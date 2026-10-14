"""Local Streamlit workbench for the same pipeline used by the CLIs."""
import json
import os
from html import escape
from pathlib import Path
import streamlit as st
from dotenv import dotenv_values
from pipeline.config import Config
from pipeline.models import Plan, Slot
from pipeline.ui_jobs import start_job, RUN_LOCK
from pipeline.ui_design import section, piece_preview, run_label
from pipeline.ui_files import EDITABLE, load_artifact, save_config, zip_run

ROOT = Path(os.getenv('SANAD_PROJECT_ROOT', Path(__file__).resolve().parent)).resolve()
OUTPUT = ROOT / 'output'
st.set_page_config(page_title='SanadSquad | Content Studio', page_icon='✦', layout='wide')
st.markdown('<style>' + (Path(__file__).parent/'assets/studio.css').read_text() + '</style>', unsafe_allow_html=True)
st.markdown('<div class="sq-top"><span class="sq-eyebrow">Workspace / Content operations</span>'
            '<span class="sq-pill">Local workspace</span></div>', unsafe_allow_html=True)
st.markdown('<div class="sq-hero"><div><div class="sq-eyebrow">SanadSquad · Content Studio</div>'
            '<h1>Your expertise.<br>A week of content.</h1>'
            '<p>Turn security knowledge into grounded posts. Plan, review and export from one workspace.</p></div>'
            '<div class="sq-hero-note"><b>Built for review.</b>Every claim has a source.<br>Every piece has a decision.</div></div>', unsafe_allow_html=True)

try:
    config = Config(ROOT)
except Exception as exc:
    st.error(f'Configuration could not be loaded: {type(exc).__name__}. Restore the configuration files and refresh.')
    st.stop()

job = st.session_state.get('job')
running = bool(job and not job.done)
env = {**dotenv_values(ROOT / '.env'), **os.environ}

with st.sidebar:
    st.markdown('<div class="sq-brand"><span class="sq-mark">S</span><div><strong>SanadSquad</strong><small>CONTENT STUDIO</small></div></div>', unsafe_allow_html=True)
    st.caption('WORKSPACE SETTINGS')
    mode = st.radio('Mode', ['Demo', 'Live'], horizontal=True, disabled=running)
    provider = st.selectbox('Provider', ['Groq', 'OpenAI'], disabled=running)
    default_model = 'openai/gpt-oss-120b' if provider == 'Groq' else 'gpt-4.1-mini'
    model = st.text_input('Model', value=default_model, key=f'model_{provider}', disabled=running)
    with st.expander('API connection', expanded=False):
        api_key = st.text_input('API key (optional override)', type='password', disabled=running,
                                help='Kept in this session only. Leave blank to use .env or the environment.')
        if env.get('OPENAI_API_KEY'):
            st.caption('Key available from your local environment. Connection is checked when you run.')
        else:
            st.caption('Demo needs no key. Live mode requires your provider key.')
        st.caption('Keys are excluded from run exports.')
    concurrency = st.slider('Concurrent pieces', 1, 6, 2, disabled=running)
    with st.expander('Usage controls'):
        budget = st.number_input('Local token budget / minute', min_value=0, max_value=1000000,
                                 value=7500 if provider == 'Groq' else 0, step=500,
                                 key=f'budget_{provider}', disabled=running)
        output_cap = st.number_input('Max completion tokens', min_value=512, max_value=8192,
                                     value=4096, step=512, disabled=running)
        retries = st.number_input('429 retries', min_value=0, max_value=6, value=3, disabled=running)
        effort = st.selectbox('Reasoning effort', ['Provider default', 'low', 'medium', 'high'], disabled=running)
        st.caption('Select an effort only if your model supports it.')
        free = st.checkbox('Using a free plan', value=provider == 'Groq', disabled=running)
        input_rate = st.number_input('Input USD / 1M tokens', min_value=0.0, value=0.0, disabled=running or free)
        output_rate = st.number_input('Output USD / 1M tokens', min_value=0.0, value=0.0, disabled=running or free)
        if not free:
            st.caption('Leaving both rates at zero reports unknown cost, not free usage.')
    st.divider()
    st.caption('YOUR WORKFLOW')
    st.caption('01  Plan your content\n\n02  Let the agents work\n\n03  Review and export')
    st.divider()
    st.caption('v1.2 · Local workspace\n\nNothing is published automatically.')

build, results, settings = st.tabs(['Create content', 'Results & history', 'Brand & instructions'])

with build:
    section('01', 'Shape your next week')
    st.caption('Set a topic, or leave it open for the research agent. Your brand rules apply to every piece.')
    try:
        default_plan = Plan.model_validate_json((ROOT/'plan.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        default_plan = Plan(slots=[Slot(id='piece_1', type='marketing', focus='')])
    a,b,c = st.columns(3)
    a.metric('Plan slots', len(default_plan.slots))
    b.metric('Technical threads', sum(x.type == 'tech-thread' for x in default_plan.slots))
    c.metric('Knowledge topics', len(config.kb))
    st.caption('Plan counts reflect the saved default. Edited rows are used when you launch.')
    edited = st.data_editor([s.model_dump() for s in default_plan.slots], num_rows='dynamic',
            hide_index=True, use_container_width=True, key='plan_editor', disabled=running,
            column_config={
                'id': st.column_config.TextColumn('Slot ID', required=True),
                'type': st.column_config.SelectboxColumn('Post type', options=list(config.types), required=True),
                'focus': st.column_config.TextColumn('Topic / focus')})
    section('02', 'Choose your run')
    scope = st.radio('What to run', ['Whole plan', 'One piece'], horizontal=True, disabled=running)
    chosen_type, chosen_topic = 'marketing', 'reentrancy'
    if scope == 'One piece':
        a, b = st.columns(2)
        chosen_type = a.selectbox('Piece type', list(config.types), disabled=running)
        chosen_topic = b.text_input('Piece topic', value='reentrancy', disabled=running)
    st.caption('Demo uses offline fixtures. Live uses your selected provider and may wait for its token budget.')
    a, b = st.columns([1, 3])
    launch = a.button('Run pipeline', type='primary', disabled=running, use_container_width=True)
    save_plan = b.button('Save plan as default', disabled=running)
    if launch or save_plan:
        try:
            plan = Plan(slots=[Slot.model_validate({**row, 'focus': row.get('focus') or ''}) for row in edited])
            if save_plan:
                if not RUN_LOCK.acquire(blocking=False):
                    raise ValueError('A UI run is active; wait before saving.')
                try:
                    temporary = ROOT/'plan.json.tmp'
                    temporary.write_text(plan.model_dump_json(indent=2)+'\n', encoding='utf-8')
                    temporary.replace(ROOT/'plan.json')
                finally:
                    RUN_LOCK.release()
                st.success('Default plan saved.')
            else:
                if scope == 'One piece':
                    plan = Plan(slots=[Slot(id='piece_1', type=chosen_type, focus=chosen_topic)])
                options = {'OPENAI_API_KEY': api_key or env.get('OPENAI_API_KEY', ''),
                    'OPENAI_BASE_URL': 'https://api.groq.com/openai/v1' if provider == 'Groq' else 'https://api.openai.com/v1',
                    'LLM_MODEL': model, 'LLM_TOKENS_PER_MINUTE': str(budget),
                    'LLM_MAX_COMPLETION_TOKENS': str(output_cap), 'LLM_RATE_LIMIT_RETRIES': str(retries),
                    'LLM_REASONING_EFFORT': None if effort == 'Provider default' else effort,
                    'INPUT_USD_PER_MILLION': str(0 if free else input_rate) if free or input_rate or output_rate else '',
                    'OUTPUT_USD_PER_MILLION': str(0 if free else output_rate) if free or input_rate or output_rate else ''}
                job = start_job(plan, ROOT, OUTPUT, mode.lower(), options, concurrency)
                st.session_state.job = job
                st.session_state.job_reported = False
                st.session_state.job_total = len(plan.slots)
                st.rerun()
        except (ValueError, OSError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f'Provider initialization failed ({type(exc).__name__}). Check the key, model and environment.')

    @st.fragment(run_every=1)
    def progress_panel():
        current = st.session_state.get('job')
        if current is None:
            st.markdown('<div class="sq-note"><strong>Ready when you are.</strong> Accepted pieces appear in Results &amp; history, with sources, review decisions and downloads.</div>', unsafe_allow_html=True)
            return
        section('03', 'Agent activity')
        events = list(current.events)
        stages = {}
        for event in events:
            if event.get('stage'):
                stages[event['slot']] = {'Slot': event['slot'], 'Stage': event['stage'],
                    'State': event.get('status', event['event'])}
        finished = sum(x['State'] in ('shipped', 'dropped', 'failed') for x in stages.values())
        st.progress(min(finished/max(st.session_state.get('job_total',1),1), 1.0),
                    text='Completed' if current.done else 'Pipeline running')
        if stages:
            st.dataframe(list(stages.values()), hide_index=True, use_container_width=True)
        if events and not current.done:
            latest = events[-1]
            if latest['event'] in ('waiting', 'retry'):
                st.info(f"Provider budget / retry wait: {latest.get('seconds', 0):.1f}s. The run is still active.")
        st.caption(f'Run: {current.output.name}' + ('' if current.done else ' · Keep the app server open while the agents work.'))
        if current.done:
            if current.error:
                st.error(current.error)
            elif current.summary:
                message = f"{current.summary['pieces_shipped']} accepted · {current.summary['pieces_dropped']} dropped/failed. Open Results & history to inspect the decisions."
                if current.summary['pieces_dropped']:
                    st.warning(message)
                else:
                    st.success(message)
            if not st.session_state.get('job_reported'):
                st.session_state.job_reported = True
                st.session_state.selected_run = str(current.output)
                st.rerun()
    progress_panel()

with results:
    section('01', 'Your content library')
    st.caption('Explore saved runs, inspect the evidence and take only accepted content forward.')
    folders = [p for p in OUTPUT.glob('*') if p.is_dir() and (p/'run_summary.json').is_file()]
    summaries = {str(p): load_artifact(p, 'run_summary.json', {}) for p in folders}
    folders.sort(key=lambda p: summaries[str(p)].get('started_at', ''), reverse=True)
    if not folders:
        st.markdown('<div class="sq-empty"><strong>Your content starts here.</strong>Run a plan from Create content. Accepted posts, sources and review decisions will appear here.</div>', unsafe_allow_html=True)
    else:
        paths = [str(p) for p in folders]
        selected = st.session_state.get('selected_run')
        index = paths.index(selected) if selected in paths else 0
        folder = Path(st.selectbox('Saved run', paths, index=index, format_func=lambda p: run_label(Path(p), summaries[p])))
        summary = summaries[str(folder)]
        usage = summary.get('usage', {})
        a,b,c,d = st.columns(4)
        a.metric('Shipped', summary.get('pieces_shipped', 0))
        b.metric('Dropped / failed', summary.get('pieces_dropped', 0))
        tokens = usage.get('input_tokens_recorded',0) + usage.get('output_tokens_recorded',0)
        c.metric('Recorded tokens', f'{tokens:,}')
        cost = usage.get('cost_usd')
        d.metric('Estimated cost', 'Unknown' if cost is None else f'${cost:.5f}')
        st.caption(f"Mode: {summary.get('mode')} · {usage.get('cost_status', '')} · Model: {usage.get('model','')}")
        if summary.get('pieces_dropped', 0):
            st.warning('This run includes rejected or failed pieces. They are excluded from the CSV; see Reviews for the reason.')
        if summary.get('mode') == 'demo':
            st.info('Demo fixtures: workflow demonstration, not a live model quality assessment.')
        if not usage.get('token_totals_complete', True):
            st.warning('Usage is incomplete; recorded totals do not include every failed call.')
        left,right = st.columns(2)
        if (folder/'posts.csv').is_file():
            left.download_button('Download posts.csv', (folder/'posts.csv').read_bytes(), 'posts.csv', 'text/csv')
        right.download_button('Download complete run ZIP', zip_run(folder), folder.name+'.zip', 'application/zip')
        st.caption('CSV groups each thread into one cell. Image cells point to specifications, not rendered images.')
        content_tab, review_tab, sources_tab, logs_tab = st.tabs(['Content & visuals','Reviews','Sources','Logs'])
        pieces = load_artifact(folder, 'final_content.json', [])
        reports = load_artifact(folder, 'review_report.json', [])
        with content_tab:
            if not pieces:
                st.info('No pieces passed in this run. Open Reviews and Logs for reasons.')
            else:
                search_col, filter_col = st.columns([3, 1])
                search = search_col.text_input('Find a piece', placeholder='Search by topic or text', key=f'search_{folder.name}')
                type_filter = filter_col.selectbox('Content type', ['All types'] + sorted({p['type'] for p in pieces}), key=f'filter_{folder.name}')
                visible = [p for p in pieces if (type_filter == 'All types' or p['type'] == type_filter)
                           and search.casefold() in (p['topic'] + ' ' + ' '.join(x['text'] for x in p['posts'])).casefold()]
                st.caption(f'{len(visible)} of {len(pieces)} accepted pieces')
                if not visible:
                    st.info('No matching content. Try another topic or clear the filters.')
                for piece in visible:
                    with st.container(border=True):
                        piece_preview(piece)
                        with st.expander('Copy text & inspect evidence'):
                            for i, post in enumerate(piece['posts'], 1):
                                st.caption(f'Post {i}')
                                st.code(post['text'], language=None)
                                st.json(post['evidence_ids'])
                        spec = (folder/piece['image_spec']).resolve()
                        if spec.is_relative_to(folder.resolve()) and spec.is_file():
                            with st.expander('Visual brief'):
                                visual = json.loads(spec.read_text(encoding='utf-8-sig'))['data']
                                st.caption('Written specification · No rendered image')
                                st.write(visual.get('prompt', ''))
                                st.caption(visual.get('alt_text', ''))
                                st.json(visual, expanded=False)
        with review_tab:
            st.caption('An editorial rejection gets one rewrite. A second rejection is dropped; a processing error is marked failed.')
            for report in reports:
                title = f"{report['slot_id']} · {report['status'].replace('shipped', 'accepted').title()}"
                with st.expander(title, expanded=report['status']!='shipped'):
                    for reason in dict.fromkeys(report.get('reasons') or []):
                        st.write('• ' + reason)
                    for review in report.get('reviews') or []:
                        st.markdown(f"**Attempt {review['attempt']}** · {'Accepted' if review['accepted'] else 'Rejected'} · {review['total']}/20")
                        scores = review.get('scores', {})
                        st.caption(' · '.join(f'{k.replace("_", " ").title()}: {v}/5' for k,v in scores.items()))
                        for reason in dict.fromkeys(review.get('reasons') or []):
                            st.write('• ' + reason)
                        with st.expander(f"Full audit · {report['slot_id']} · attempt {review['attempt']}"):
                            st.json(review)
        with sources_tab:
            st.json(load_artifact(folder, 'research_log.json', []))
        with logs_tab:
            for name in ('run_summary.json','usage.json','events.json','resolved_plan.json'):
                with st.expander(name):
                    st.json(load_artifact(folder,name,{}))

with settings:
    section('01', 'Make it sound like your brand')
    st.caption('Tune the voice, source material and editorial instructions. Validated changes apply to future runs.')
    st.markdown('<div class="sq-note"><strong>Your rules, preserved.</strong> Every run saves the exact instructions it used. Editing here does not change past results.</div>', unsafe_allow_html=True)
    filename = st.selectbox('Configuration file', EDITABLE, disabled=running)
    with st.form('config_form'):
        text = st.text_area('Contents', config.read(filename), height=400, key=f'edit_{filename}', disabled=running)
        submitted = st.form_submit_button('Validate & save', disabled=running)
    if submitted:
        if not RUN_LOCK.acquire(blocking=False):
            st.error('Wait for the active UI run to finish before saving configuration.')
        else:
            try:
                save_config(ROOT, filename, text)
                st.success('Validated and saved. The next run will use these instructions.')
            except Exception as exc:
                st.error(f'Not saved: {exc}')
            finally:
                RUN_LOCK.release()

st.markdown('<div class="sq-footer"><span>SanadSquad / Content Studio</span><span>Grounded content · Human review before publishing</span></div>', unsafe_allow_html=True)
