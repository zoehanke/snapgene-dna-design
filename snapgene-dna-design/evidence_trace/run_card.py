"""Read-only English overview of recorded sources, calls, files and scoped checks."""
import html
import re
from collections import Counter
from pathlib import Path


def _text(value):return html.escape(str(value if value is not None else ''),quote=True)
def _name(path):return re.split(r'[\\/]',str(path))[-1]
def _sha(value):return isinstance(value,str) and bool(re.fullmatch('[a-fA-F0-9]{64}',value))


def _input_hashes(value):
    if isinstance(value,dict):
        for key in ('sha256','source_sha256'):
            if _sha(value.get(key)):yield value[key].lower()
        for child in value.values():yield from _input_hashes(child)
    elif isinstance(value,list):
        for child in value:yield from _input_hashes(child)


def _native_fact(value):
    if not isinstance(value,dict):return None
    inner=value.get('result') if isinstance(value.get('result'),dict) else value
    analysis=inner.get('analysis',{})
    if not isinstance(analysis,dict):analysis={}
    if analysis.get('direction_status'):
        spacer=analysis.get('spacer'); identity=''
        if isinstance(spacer,dict):identity=str(spacer.get('length','?'))+' nt / sequence fingerprint '+str(spacer.get('sha256','unrecorded'))[:8]
        elif isinstance(spacer,str):identity=spacer
        matches=analysis.get('target_matches',[])
        sites='; '.join('target '+str(row.get('protospacer_parts_0based'))+', PAM '+str(row.get('pam')) for row in matches)
        return (4,'Guide '+str(analysis['direction_status'])+' · '+identity+'. '+sites)
    route=analysis.get('preparation_route')
    if isinstance(route,dict):return (3,'Preparation '+str(route.get('status'))+'; sequence simulation '+str(route.get('simulation_status'))+'; wet experiment '+str(route.get('wet_lab','not recorded'))+'.')
    size=analysis.get('amplicon_length')
    if size is not None:return (2,'Exact PCR prediction: '+str(size)+' bp; not a measured band.')
    products=inner.get('products',[]) if analysis.get('result_kind') not in ('verification','primers','protocol') else []
    lengths=[product.get('sequence',{}).get('length') for product in products if isinstance(product,dict) and isinstance(product.get('sequence'),dict)]
    if lengths and all(length is not None for length in lengths):return (2,'Computed molecular product: '+', '.join(map(str,lengths))+' bp. Not a wet preparation.')
    if value.get('status') in ('SUPPORTED','CONTRADICTED','INSUFFICIENT','NOT_TESTED'):
        return (5,str(value['status'])+': '+str(value.get('reason') or value.get('scope') or 'Scoped returned result.'))
    return None


def _citations(value):
    if isinstance(value,dict):
        if isinstance(value.get('url'),str) and value.get('name') and (value.get('source_type') or value.get('type')):
            yield value
        for child in value.values():yield from _citations(child)
    elif isinstance(value,list):
        for child in value:yield from _citations(child)


def _lab_flags(value):
    if isinstance(value,dict):
        if value.get('wet_lab')=='NOT_PERFORMED':yield 'Wet experiments: NOT_PERFORMED.'
        for child in value.values():yield from _lab_flags(child)
    elif isinstance(value,list):
        for child in value:yield from _lab_flags(child)


def project_card(graph):
    """Project existing facts only. Never mutate the graph or infer a causal edge."""
    records=graph.get('source_records',{})
    events=sorted((row for row in records.values() if row.get('event_type')),key=lambda row:row.get('sequence',0))
    runs=graph.get('runs',[])
    groups=[];by_run={};event_groups={}
    # Prior organization text is already a saved reading projection. It remains
    # tied to exact event references when several invocations share one journal.
    descriptions={}
    for event in graph.get('audit_events',[]):
        if event.get('event_type')=='organization_recorded':
            for step in event['payload'].get('design_process',{}).get('steps',{}).values():
                for ref in step.get('source_refs',[]):descriptions[ref]=step.get('content','')
    declared=[];not_done=[]
    for index,run in enumerate(runs,1):
        own=[event for event in events if event.get('run_id')==run['id']]
        returned=[event for event in own if event['event_type']=='stage_completed' and isinstance(event.get('payload',{}).get('result'),dict)]
        outcomes=[event['payload']['result'] for event in returned if event['payload'].get('stage')=='outcome']
        outcome=outcomes[-1] if outcomes else {}
        title=str(outcome.get('kit') or run.get('route') or 'Recorded call').replace('_',' ')
        group={'id':'call-'+str(index),'run_id':run['id'],'application':outcome.get('kit'),'calls':1,'title':title,'status':str(outcome.get('status') or run.get('status','unknown')),
               'summary':outcome.get('report_summary') or '', 'facts':[],'hashes':[],'sequence':index}
        candidates=[]
        for event in own:
            event_groups[event.get('event_id')]=group['id']
            value=event.get('payload',{}).get('result')
            not_done[:0]=list(_lab_flags(value))
            fact=_native_fact(value)
            if fact:candidates.append(fact)
            elif event.get('event_id') in descriptions:
                sentence=descriptions[event['event_id']]
                if sentence and not sentence.startswith(('Program completed','程序完成')):candidates.append((1,sentence))
        # Show the last scoped finding of each useful category, retaining every
        # omitted record in the full view rather than truncating its text.
        for priority in (5,4,3,2,1):
            values=list(dict.fromkeys(text for rank,text in candidates if rank==priority))
            if values:
                group['facts'].extend(values[-2:] if priority==2 else values[-1:])
            if len(group['facts'])>=3:break
        group['facts']=group['facts'][:3]
        for value in outcomes:
            not_done.extend(value.get('report_unverified_scope',[]))
            if value.get('wet_lab')=='NOT_PERFORMED':not_done.append('Wet experiments: NOT_PERFORMED.')
        groups.append(group);by_run[run['id']]=group
    if not groups:
        groups=[{'id':'call-1','run_id':None,'title':'No recorded call','status':'unknown','summary':'No execution record is available.',
                 'facts':[],'hashes':[],'sequence':1}]
    merged=[];aliases={}
    for group in groups:
        if merged and group.get('application') and group['application']==merged[-1].get('application'):
            previous=merged[-1];aliases[group['id']]=previous['id'];previous['calls']+=group['calls']
            previous['facts']=list(dict.fromkeys(previous['facts']+group['facts']))
            previous['status']='latest: '+group['status'];by_run[group['run_id']]=previous
        else:
            group['sequence']=len(merged)+1;merged.append(group);aliases[group['id']]=group['id']
    groups=merged
    event_groups={key:aliases[value] for key,value in event_groups.items()}
    relations=[];supported={};participating=set();cross_run_files=set();cross_content=set();cross_hashes={}
    for fact in graph.get('fact_relations',[]):
        if not (fact.get('kind')=='input_reference' and fact.get('origin')=='program_derived' and
                fact.get('scope')=='same_file_content' and fact.get('verification_method')=='sha256_equality' and _sha(fact.get('sha256'))):continue
        artifact=records.get(fact.get('from'),{});consumer=records.get(fact.get('to'),{})
        producer=records.get(artifact.get('result_event_ref'),{})
        payload=consumer.get('payload',{})
        inputs=payload.get('input_files',[]) if 'input_files' in payload else payload.get('input',{})
        digest=fact['sha256'].lower()
        if artifact.get('kind')!='artifact' or str(artifact.get('sha256','')).lower()!=digest or digest not in set(_input_hashes(inputs)):continue
        source=event_groups.get(producer.get('event_id'));target=event_groups.get(consumer.get('event_id'))
        if not source or not target:continue
        key=(source,target)
        edge=supported.setdefault(key,{'from':source,'to':target,'kind':'grouped_with','verified':True,'fact_relation_ids':[],
                                      'hashes':[],'files':[],'label':'SHA-256-equal output / declared input'})
        edge['fact_relation_ids'].append(fact['id'])
        if digest not in edge['hashes']:edge['hashes'].append(digest)
        filename=_name(artifact.get('path','recorded file'))
        if filename not in edge['files']:edge['files'].append(filename)
        participating.add(fact['from'])
        if source!=target:
            cross_run_files.add(fact['from'])
            cross_content.add((artifact.get('path'),artifact.get('sha256')))
            for group_id in (source,target):cross_hashes.setdefault(group_id,[]).append(digest)
        for group_id in (source,target):
            group=next(row for row in groups if row['id']==group_id)
            if digest not in group['hashes']:group['hashes'].append(digest)
    relations.extend(supported.values())
    for group in groups:group['hashes']=list(dict.fromkeys(cross_hashes.get(group['id'],[])+group['hashes']))
    sources=[];source_keys={};seen_sources={}
    for node in graph.get('nodes',[]):
        if node.get('kind')!='source':continue
        kind=str(node.get('source_type','declared-source'))
        path=node.get('path');digest=node.get('source_sha256')
        # A prediction file that already has a genuine producer/input equality
        # fact is an intermediate, not a newly fetched external source.
        if kind=='provided-prediction-table' and any(str(records.get(ref,{}).get('sha256','')).lower()==str(digest).lower() for ref in participating):continue
        identity=(kind,str(path or node.get('title')),str(digest))
        if identity not in seen_sources:
            category=('Public database record' if kind.startswith('public-database') else
                      'Reported observations' if kind=='researcher-reported-observations' else 'User file' if path else 'Declared source')
            item={'id':'source-'+str(len(sources)+1),'title':node.get('title') or _name(path or 'Source'),
                  'category':category,'sha256':digest if _sha(digest) else None,'path':path,
                  'scope':node.get('scope') or node.get('verification',{}).get('scope') or 'Source identity is declared; file checks do not establish experimental identity.'}
            sources.append(item);seen_sources[identity]=item
        source_keys[node.get('key')]=seen_sources[identity]['id']
        if node.get('verification_status')!='verified':declared.append(node.get('title','Unverified source'))
    for run in runs:
        group=by_run[run['id']]
        for ref in run.get('context_refs',[]):
            if ref in source_keys:
                relations.append({'from':source_keys[ref],'to':group['id'],'kind':'contextualize','verified':False,
                                  'fact_relation_ids':[],'hashes':[],'label':'Declared input/context; not a causal claim'})
                node=records.get(ref,{})
                if _sha(node.get('source_sha256')) and node['source_sha256'] not in group['hashes']:group['hashes'].append(node['source_sha256'])
    for source in sources:
        if not source.get('path') or not source.get('sha256'):continue
        for event in events:
            inputs=event.get('payload',{}).get('input_files',[])
            if any(row.get('path')==source['path'] and row.get('sha256')==source['sha256'] for row in inputs):
                target=event_groups.get(event.get('event_id'))
                if target:relations.append({'from':source['id'],'to':target,'kind':'contextualize','verified':False,
                    'fact_relation_ids':[],'hashes':[],'label':'Declared file input; no prior output/input hash fact'})
    citations={}
    for event in events:
        if event.get('event_type') not in ('stage_completed','file_operation_completed'):continue
        for citation in _citations(event.get('payload',{}).get('result')):
            identity=(citation.get('name'),citation['url'])
            if identity not in citations:
                item={'id':'citation-'+str(len(citations)+1),'title':str(citation['name']),'category':'Sourced knowledge / declared citation',
                      'sha256':None,'path':None,'scope':'Citation supplied by the calculation; not fetched or independently verified in this run.'}
                citations[identity]=item;sources.append(item);declared.append(str(citation['name']))
                target=event_groups.get(event.get('event_id'))
                if target:relations.append({'from':item['id'],'to':target,'kind':'contextualize','verified':False,'fact_relation_ids':[],
                                            'hashes':[],'label':'Declared citation; no retrieval or scientific support is inferred'})
    output_by_path={}
    for node in graph.get('nodes',[]):
        if node.get('kind')!='artifact':continue
        key=(node.get('path'),node.get('sha256'));previous=output_by_path.get(key)
        def role_rank(item):return 0 if item.get('role')=='authoritative' else 1 if item.get('role')=='candidate-file' else 2 if item.get('role')=='supporting-file' else 3
        if previous and role_rank(previous)<=role_rank(node):continue
        output_by_path[key]=node
    def output_priority(node):
        priority=0 if node.get('role')=='authoritative' else 1 if (node.get('path'),node.get('sha256')) in cross_content else 2 if 'candidate' in str(node.get('role')) else 3
        return priority,node.get('recorded_sequence',0)*(1 if priority<=1 else -1)
    outputs=[{'title':_name(node.get('path','file')),'path':node.get('path'),'sha256':node.get('sha256'),
              'role':node.get('role','recorded file'),'key':node.get('key')} for node in sorted(output_by_path.values(),key=output_priority)]
    checks=[]
    for node in graph.get('nodes',[]):
        if node.get('kind')=='validation':
            details=node.get('details',{});check=details.get('check',{}) if isinstance(details,dict) else {}
            checks.append({'name':node.get('check','Recorded check'),'status':str(node.get('result','unknown')),
                           'detail_status':check.get('details',{}).get('status') if isinstance(check.get('details'),dict) else None,
                           'scope':node.get('scope') or check.get('scope') or 'Scope retained in the technical record.'})
    decisions=[node.get('text','') for node in graph.get('nodes',[]) if node.get('kind') in ('decision','statement','claim')]
    declared.extend(decisions)
    distinct_relations={}
    for edge in relations:
        key=(edge['from'],edge['to'],edge['verified'],edge['kind'])
        distinct_relations.setdefault(key,edge)
    goal=next((node.get('text','') for node in graph.get('nodes',[]) if node.get('kind')=='requirement'),'')
    return {'title':graph.get('report',{}).get('title') or 'Recorded execution','first_goal':goal, 'sources':sources,'steps':groups,'outputs':outputs,
            'relations':list(distinct_relations.values()),'checks':checks,'declared':list(dict.fromkeys(str(row) for row in declared if row)),
            'not_done':list(dict.fromkeys(str(row) for row in not_done if row)),
            'scope':'Records actual operations and declared inputs. This does not prove that scientific conclusions are correct.'}


def card_html(card):
    def node(item,body):return '<article class="rc-node" id="rc-'+_text(item['id'])+'">'+body+'</article>'
    categories={}
    for source in card['sources']:categories.setdefault(source['category'],[]).append(source)
    source_html=''
    for category,items in categories.items():
        entries=[]
        for item in items:
            fingerprint=('<code>SHA-256 '+_text(item['sha256'][:8])+'</code>' if item['sha256'] else
                         '<code>No file hash recorded.</code>' if any(row['sha256'] for row in items) else '')
            entries.append('<div class="rc-source-entry" id="rc-'+_text(item['id'])+'"><b>'+_text(item['title'])+'</b>'+fingerprint+'</div>')
        no_hash='<code>No file hash recorded for these declarations.</code>' if all(not item['sha256'] for item in items) else ''
        source_html+='<div class="rc-source-pack"><small>'+_text(category)+' · '+str(len(items))+'</small>'+''.join(entries[:8])+no_hash
        if len(entries)>8:source_html+='<details><summary>'+str(len(entries)-8)+' additional sources</summary>'+''.join(entries[8:])+'</details>'
        source_html+='</div>'
    if not source_html:source_html='<p>No external source node was recorded.</p>'
    step_html=''
    for step in card['steps']:
        hashes=' · '.join(value[:8] for value in step['hashes'][:3]) or 'No file hash recorded'
        body_facts=[text for text in step['facts'] if not text.startswith(('SUPPORTED:','CONTRADICTED:','INSUFFICIENT:','NOT_TESTED:'))]
        facts=''.join('<p>'+_text(text)+'</p>' for text in body_facts)
        if not body_facts and step['facts']:facts='<p>Recorded comparison results appear under Scoped conclusions.</p>'
        internal=[edge for edge in card['relations'] if edge['verified'] and edge['from']==edge['to']==step['id']]
        if internal:facts+='<p class="rc-internal" data-verified-file-link="true">'+str(sum(len(edge['fact_relation_ids']) for edge in internal))+' internal file-hash matches</p>'
        for edge in card['relations']:
            if edge['verified'] and edge['from']==step['id'] and edge['to']!=step['id']:
                target=next(row for row in card['steps'] if row['id']==edge['to'])
                facts+='<p class="rc-file-link" data-verified-file-link="true">File match to step '+str(target['sequence'])+': '+_text(', '.join(edge.get('files',[])))+' · SHA-256 '+_text(edge['hashes'][0][:8])+'</p>'
        count=' ('+str(step.get('calls',1))+' calls)' if step.get('calls',1)>1 else ''
        state=str(step['status']).lower().split()[-1]
        step_html+=node(step,'<div class="rc-node-top"><b>'+str(step['sequence'])+' · '+_text(step['title'])+count+'</b><span class="rc-status" data-state="'+_text(state)+'">'+_text(step['status'])+'</span></div>'+facts+'<code>Files: '+_text(hashes)+'</code>')
    output_html=''
    for item in card['outputs'][:5]:
        href=Path(item['path']).as_uri() if item.get('path') and Path(item['path']).is_absolute() else '#full-view'
        output_html+='<article class="rc-file"><a href="'+_text(href)+'">'+_text(item['title'])+'</a><small>'+_text(item['role'])+'</small><code>SHA-256 '+_text(str(item.get('sha256') or 'unrecorded')[:8])+'</code></article>'
    outcomes=[text for step in card['steps'] for text in step['facts'] if text.startswith(('SUPPORTED:','CONTRADICTED:','INSUFFICIENT:','NOT_TESTED:'))]
    if outcomes:output_html+='<h3>Scoped conclusions</h3>'+''.join('<p class="rc-conclusion">'+_text(text)+'</p>' for text in outcomes)
    counts=Counter(row['status'] for row in card['checks'])
    check_text=', '.join(str(count)+' '+status for status,count in sorted(counts.items())) or 'No scoped program checks recorded.'
    passing=list(dict.fromkeys(row['name'] for row in card['checks'] if row['status'].lower() in ('passed','pass','true','verified')))
    if passing:check_text+=' Checked: '+', '.join(passing[:4])+('. Additional scopes remain in Full view.' if len(passing)>4 else '.')
    check_examples='; '.join(row['name'].replace('_',' ')+': '+row['status']+(' ('+str(row['detail_status'])+')' if row.get('detail_status') else '') for row in card['checks'] if row['status'].lower() not in ('passed','pass','true','verified','not_applicable'))
    declarations='; '.join(card['declared'][:4]) or 'Submitted goals, reference identity and source applicability remain declarations.'
    limits='; '.join(card['not_done'][:5]) or 'No independent experiment or scientific-truth verification is established by this record.'
    return '<section id="run-card" lang="en"><header class="rc-header"><div><small>Evidence Trace · captured execution</small><h1>Run card</h1><p>'+_text(card.get('first_goal') or card['title'])+'</p></div><a class="rc-full" href="?view=full" data-open-full>Technical details / Full view</a></header><h2>Data chain</h2><p class="rc-legend"><span class="rc-solid-key"></span>Solid: SHA-256-equal output/input files. <span class="rc-dashed-key"></span>Dashed: declared inputs or citations. Neither means scientific causality.</p><div class="rc-flow"><svg class="rc-lines" aria-hidden="true"></svg><div class="rc-column"><h3>External sources</h3>'+source_html+'</div><div class="rc-column"><h3>Recorded steps</h3>'+step_html+'</div><div class="rc-column"><h3>Files and scoped outcomes</h3>'+output_html+'<p>All '+str(len(card['outputs']))+' recorded file versions remain in Full view.</p></div></div><table class="rc-summary"><tbody><tr><th>Program-verified checks</th><td>'+_text(check_text)+('<br>'+_text(check_examples) if check_examples else '')+'</td></tr><tr><th>Declared statements</th><td>'+_text(declarations)+'</td></tr><tr><th>Not checked or not performed</th><td>'+_text(limits)+'</td></tr></tbody></table><p class="rc-scope">'+_text(card['scope'])+'</p></section>'


def card_markdown(card):
    lines=['# Run card','',card.get('first_goal') or card['title'],'','## Data chain','',
           'Solid links: recorded output/input SHA-256 equality only. Dashed links: declared inputs/citations. No scientific causality.','']
    for source in card['sources']:lines.append('- Source: '+source['title']+'; '+('SHA-256 '+source['sha256'][:8] if source['sha256'] else 'no file hash recorded')+'.')
    for step in card['steps']:
        lines+=['',str(step['sequence'])+'. '+step['title']+' · '+step['status'],*('   '+text for text in step['facts'])]
    lines+=['','| Category | Recorded scope |','|---|---|',
            '| Program-verified checks | '+str(len(card['checks']))+' scoped checks; successes/failures remain in Full view. |',
            '| Declared statements | '+('; '.join(card['declared'][:4]) or 'Source identity and submitted explanations remain declarations.') .replace('|','\\|')+' |',
            '| Not checked or not performed | '+('; '.join(card['not_done'][:5]) or 'No independent experiment authentication.').replace('|','\\|')+' |','',card['scope'],'']
    return '\n'.join(lines)
