"""Community presentation of actual API responses; no retrieval or Critic rules."""
import json
import re
import streamlit as st
from pydantic import ValidationError
from hydroguard.services.investigation import RunRequest
from hydroguard.ui.client import AuditClient, BackendError

DEFAULT = {'project_claim':{'claim_id':'water-claim','project_name':'Fictional Philippine Development',
           'text':'Project water demand will not significantly affect existing water users.'},
           'domain':'Water','case_context':{'stage':'scoping','community_notes':'Synthetic community context.'},
           'evidence_references':[]}
PAGES = ['Case workspace','Investigation results','Evidence explorer','Consultation brief']


def display(value):
    """Avoid rendering credential-like strings or absolute local paths."""
    text = str(value or '')
    text = re.sub(r'(?:nvapi-|sk-proj-|ghp_)[A-Za-z0-9_-]+', '[credential omitted]', text)
    text = re.sub(r'(?i)bearer\s+\S+', '[credential omitted]', text)
    text = re.sub(r'(?:/Users/|/home/|/private/|[A-Za-z]:\\)[^\s,;]+', '[local path omitted]', text)
    return text


def source_details(result):
    if not result.citations:
        st.info('No source records were returned. This does not prove evidence does not exist.')
    for source in result.citations:
        with st.expander(display(source.document_title)):
            st.text(display(f'Source: {source.source_id}\nDocument: {source.document_id}\nChunk: {source.chunk_id}'))
            st.write(display(f'Page: {source.page}' if source.page else f'Location: {source.locator or "not supplied"}'))
            st.write(display(f'Type: {source.source_type or source.kind} · Provenance: {source.provenance}'))
            if source.provenance == 'synthetic' or source.is_synthetic:
                st.text(display(source.text))
            else:
                st.caption('Private source text is withheld here. Review the original through your authorized evidence process.')
    for basis in result.audit.assessment_bases:
        with st.expander('Assessment basis · ' + display(basis.basis_id)):
            st.text(display(basis.model_dump_json(indent=2)))


def brief(result):
    approved = result.gate.passed
    lines = ['HYDROGUARD CONSULTATION BRIEF', display(result.audit.claim.project_name),
             'Mode: ' + display(result.audit.mode), 'Run: ' + result.run_id,
             'Project claim: ' + display(result.audit.claim.text),
             'Validated finding:' if approved else 'UNRESOLVED — not an established conclusion:',
             display(result.finding.text), 'Evidence strength: ' + result.finding.strength.value,
             'Gate: ' + ('passed for this finding only' if approved else 'blocked'),
             'Limitations:', *[display(x) for x in result.finding.limitations],
             'Gaps:', *[display(x) for x in result.finding.gaps],
             'Question: ' + (display(result.community_question) if approved else 'No gate-approved question available.'),
             'Sources:']
    lines += [display(f'{s.source_id} | {s.document_title} | page {s.page or "not supplied"} | {s.chunk_id} | {s.provenance}') for s in result.citations]
    lines += ['Missing evidence is not proof of harm or illegality. Gate approval is not project safety approval.']
    return '\n\n'.join(lines)


def render():
    st.set_page_config(page_title='HydroGuard · Evidence workspace',page_icon='🌿',layout='wide')
    st.markdown('''<style>
    .stApp {background:#f7f9f7;color:#152f40} h1,h2,h3 {color:#123a48}
    .stMainBlockContainer {max-width:1180px;padding-top:2rem}
    [data-testid="stSidebar"] {background:#e7f0ec}
    div[data-testid="stMetric"] {background:#edf4f1;border-radius:12px;padding:16px}
    .stButton>button[kind="primary"] {background:#006f70;color:white;border:0}
    </style>''',unsafe_allow_html=True)
    st.title('HydroGuard')
    st.caption('See the claim. Trace the evidence. Challenge the gap. Know what to ask next.')
    st.session_state.setdefault('case',json.loads(json.dumps(DEFAULT)))
    page = st.sidebar.radio('Workspace',PAGES)
    st.sidebar.caption('1. Describe a case → 2. Audit → 3. Explore → 4. Prepare')
    try:
        client = AuditClient()
        health = client.health()
    except BackendError as error:
        st.error(str(error)); st.info('Start FastAPI with SAMPLE_MODE=true python run.py.'); return
    sample = health['mode']=='sample'
    st.sidebar.info('SAMPLE · synthetic evidence / offline rules' if sample else 'LIVE · Zetaris retrieval only')
    st.sidebar.caption('Nemotron inference blocked/unverified. World Model not integrated.')
    result = st.session_state.get('result')
    if result and (result.audit.mode.startswith('Sample') != sample):
        st.warning('Saved result belongs to a different mode. Run a new audit for the current backend.')
    if page == PAGES[0]:
        st.subheader('Your case workspace')
        st.write('Start with a project assurance. We check the reviewed evidence and help identify what to ask next.')
        case=st.session_state['case']
        with st.form('case_form'):
            name=st.text_input('Project name',value=case['project_claim']['project_name'],max_chars=500)
            domain=st.selectbox('Environmental domain',['Water','Land','Air','People'],index=['Water','Land','Air','People'].index(case['domain']))
            claim=st.text_area('Project claim',value=case['project_claim']['text'],height=110,max_chars=10000)
            notes=st.text_area('Community concerns (optional)',value=case['case_context']['community_notes'],max_chars=10000,
                               help='Avoid personal identifiers. Current offline rules do not interpret these notes.')
            stage=st.selectbox('Consultation stage',['scoping','consultation','review'],index=['scoping','consultation','review'].index(case['case_context']['stage']))
            st.caption('Prefilled Water case is fictional. People and document upload are not supported by this API yet. Live mode currently supports a bounded Water investigation.')
            submitted=st.form_submit_button('Run Evidence Audit',type='primary')
        if submitted:
            if domain=='People' or (not sample and domain!='Water'):
                st.warning('This domain is not available in the current backend mode.'); return
            payload={'project_claim':{'claim_id':case['project_claim']['claim_id'],'project_name':name,'text':claim},
                     'domain':domain,'case_context':{'stage':stage,'community_notes':notes},'evidence_references':[]}
            st.session_state['case']=payload
            st.session_state.pop('result',None)
            try:
                request=RunRequest.model_validate(payload)
                with st.spinner('Auditing evidence through the HydroGuard API…'):
                    st.session_state['result']=client.run(request)
                st.success('Audit returned. Open Investigation results to review the gate and sources.')
            except ValidationError:
                st.error('Enter a project name and a nonblank project claim.')
            except BackendError as error:
                st.error(str(error))
        return
    if page == PAGES[2]:
        st.subheader('Live Zetaris Knowledge Explorer')
        st.caption('Search genuine regulatory source passages. This is a document lookup, not a claim verdict or AI chatbot.')
        if sample:
            st.warning('Live search is disabled in sample mode. Start the API with SAMPLE_MODE=false and valid Zetaris configuration.')
            return
        with st.form('live_zetaris_search'):
            search_domain = st.selectbox('Environmental domain', ['Water', 'Land', 'Air'])
            query = st.text_input('Search terms', value='water users',
                help='Use supported topic keywords. For Water: water, groundwater, baseline, season, demand, users.')
            submitted_search = st.form_submit_button('Search Zetaris', type='primary')
        if submitted_search:
            try:
                with st.spinner('Querying Zetaris for regulatory evidence…'):
                    st.session_state['zetaris_search'] = client.search(query, search_domain)
            except BackendError as error:
                st.session_state.pop('zetaris_search', None)
                st.error(str(error))
        searched = st.session_state.get('zetaris_search')
        if searched:
            st.success('Live Zetaris query completed. This does not verify a project claim.')
            st.metric('Retrieved source records', searched['result_count'])
            st.caption('Matched topics: ' + ', '.join(searched['supported_terms_used']))
            if not searched['results']:
                st.info('No matching passages were returned for these topics.')
            for i, source in enumerate(searched['results'], 1):
                title = display(source.get('document_title', 'Untitled source'))
                with st.expander(f'{i}. {title} · page {source.get("page") or "not supplied"}'):
                    st.caption('Source ID: ' + display(source.get('source_id')))
                    st.caption('Document ID: ' + display(source.get('document_id')))
                    st.caption('Source type: regulatory · Origin: live Zetaris')
                    st.write(display(source.get('text', '')))
        return
    if not result:
        st.info('Run an evidence audit in Case workspace first.'); return
    st.caption('Run ' + result.run_id + ' · ' + display(result.audit.mode))
    if page == PAGES[1]:
        st.subheader('What does the evidence establish?')
        cols=st.columns(3)
        cols[0].metric('Evidence strength',result.finding.strength.value)
        cols[1].metric('Finding gate','Passed' if result.gate.passed else 'Blocked')
        cols[2].metric('Sources reviewed',len(result.citations))
        if not result.gate.passed:st.warning('Unresolved review item — do not use this as an established conclusion.')
        st.text(display(result.finding.text))
        st.info('Insufficient evidence does not demonstrate harm. Gate approval validates this qualified finding, not project safety or compliance.')
        st.subheader('Evidence gaps')
        for gap in result.finding.gaps:st.write('• '+display(gap))
        for limitation in result.finding.limitations:st.caption(display(limitation))
        st.subheader('Review controls')
        if result.critic:
            st.write(display(f'Critic: {result.critic.response_origin} · Decision: {result.critic.decision}'))
            st.caption(display(result.critic.model_identity))
        else:st.warning('No Critic approval was returned. Live Nemotron execution is not verified.')
        for reason in result.gate.reasons:st.write(display(reason))
        st.subheader('Consultation question')
        st.text(display(result.community_question) if result.gate.passed and result.community_question else 'No validated consultation question is available.')
        source_details(result)
    else:
        st.subheader('Prepare for consultation')
        text=brief(result)
        st.text(text)
        st.download_button('Download text brief',text,'hydroguard-brief.txt','text/plain')
        # Deliberately omit private full text and community notes from exports.
        summary={'run_id':result.run_id,'status':result.status,'gate_passed':result.gate.passed,'brief':text}
        st.download_button('Download JSON brief',json.dumps(summary,indent=2),'hydroguard-brief.json','application/json')
        st.caption('Editable text and JSON only. DOCX report generation is not implemented.')
