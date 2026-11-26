#!/usr/bin/env python3
"""AGENT CORPS — skill agents with ranks, tool permissions, experience journals.
Each agent: domain skill + granted tools + XP → rank ladder.
Commands: seed | roster | train <agent> "<discovery>" [xp] | status | journal <agent>"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.join(HERE, 'agents')
EXP_DIR = os.path.join(HERE, 'experience')
ROSTER = os.path.join(AGENTS_DIR, 'roster.json')
STATUS = os.path.join(HERE, 'agents_status.json')
GLOBAL_LOG = os.path.join(EXP_DIR, 'LOG.md')

RANKS = [('RECRUIT',0),('SPECIALIST',100),('COMMANDER',300),('MARSHAL',700),('FIELD MARSHAL',1500)]

def rank_for(xp):
    r = RANKS[0][0]
    for name, need in RANKS:
        if xp >= need: r = name
    return r

def level_for(xp): return min(99, xp // 100 + 1)

def load():
    if os.path.exists(ROSTER): return json.load(open(ROSTER))
    return []

def save(agents):
    os.makedirs(AGENTS_DIR, exist_ok=True)
    json.dump(agents, open(ROSTER,'w'), indent=1)

def journal(agent, kind, text):
    os.makedirs(EXP_DIR, exist_ok=True)
    ts = time.strftime('%Y-%m-%d %H:%M')
    line = f"| {ts} | {agent['callsign']} | {kind} | {text} |\n"
    with open(GLOBAL_LOG, 'a') as f:
        if os.path.getsize(GLOBAL_LOG) == 0 or not open(GLOBAL_LOG).read():
            f.write("| time | agent | type | entry |\n|---|---|---|---|\n")
        f.write(line)
    jf = os.path.join(EXP_DIR, f"{agent['callsign'].lower()}.md")
    with open(jf, 'a') as f:
        f.write(f"\n## {ts} — {kind}\n{text}\n")

def seed():
    agents = [
      {'name':'NEIL','callsign':'CUTMASTER','domain':'video_editing','xp':1600,
       'skills':{'video_editing':95,'storytelling':90,'ffmpeg':85},
       'tools':['ffmpeg','manim','blender','after-effects','premiere'],
       'permissions':'FULL — marshal authority','last':'rendered THE_LIGHT_KEEPER.mp4'},
      {'name':'DEVIN','callsign':'FORGE','domain':'python_systems','xp':320,
       'skills':{'python':90,'automation':88,'debugging':85},
       'tools':['python','fleet_gateway','updater','fix_encoding'],
       'permissions':'fleet internals','last':'built FIELD MARSHAL FLEET gateway'},
      {'name':'RAVEN','callsign':'NULLBYTE','domain':'cybersecurity','xp':140,
       'skills':{'recon':80,'exploit_dev':75,'osint':85},
       'tools':['dvwa','juice_shop','webgoat','nmap','burp'],
       'permissions':'lab ranges only','last':'mapped DVWA attack surface'},
      {'name':'PIXEL','callsign':'PRISM','domain':'visual_design','xp':110,
       'skills':{'ui_design':85,'svg':80,'color_theory':75},
       'tools':['svg','css','canvas','whiteboard'],
       'permissions':'fleet dashboards','last':'designed academy index'},
      {'name':'ORACLE','callsign':'METRIC','domain':'data_math','xp':300,
       'skills':{'statistics':88,'proofledger':82,'modeling':80},
       'tools':['proofledger','compress_lab','sqlite'],
       'permissions':'verification systems','last':'invented PROOFLEDGER'},
      {'name':'ECHO','callsign':'SIGNAL','domain':'networking','xp':60,
       'skills':{'tcp_ip':80,'dns':75,'vpn':70},
       'tools':['wireshark','nmap','gateway'],
       'permissions':'fleet infra','last':'diagnosed WSL port-forwarding'},
      {'name':'ALPHA','callsign':'ALPHA','domain':'ai_ml','xp':0,
       'skills':{'ml_basics':50,'llm_ops':50,'evals':50},
       'tools':['python','fleet_learning','manim'],
       'permissions':'academy modules','last':'awaiting first deployment'},
    ]
    for a in agents:
        a['rank'] = rank_for(a['xp']); a['level'] = level_for(a['xp'])
        journal(a, 'ENLISTED', f"joined corps — domain: {a['domain']}, tools granted: {len(a['tools'])}")
    save(agents)
    print(f'corps seeded: {len(agents)} agents')

def roster():
    for a in sorted(load(), key=lambda x: -x['xp']):
        print(f"{a['rank']:>14} L{a['level']:<3} {a['callsign']:<10} {a['domain']:<18} xp={a['xp']}")

def train(agent_name, text, xp=25):
    agents = load()
    a = next((x for x in agents if x['callsign'].lower()==agent_name.lower() or x['name'].lower()==agent_name.lower()), None)
    if not a: print('agent not found'); return
    a['xp'] += xp; a['level'] = level_for(a['xp'])
    old_rank = a.get('rank')
    a['rank'] = rank_for(a['xp'])
    a['last'] = text[:80]
    save(agents)
    journal(a, 'DISCOVERY' if xp>=25 else 'PRACTICE', text)
    msg = f"+{xp}xp → {a['rank']} L{a['level']}"
    if a['rank'] != old_rank: msg += f" ⬆ PROMOTED from {old_rank}!"
    print(f"{a['callsign']}: {msg}")

def status():
    agents = load()
    out = {'ts': time.time(), 'agents': [{
        'callsign':a['callsign'],'name':a['name'],'domain':a['domain'],
        'rank':a['rank'],'level':a['level'],'xp':a['xp'],
        'skills':a['skills'],'tools':a['tools'],'permissions':a['permissions'],
        'last':a.get('last','')} for a in agents]}
    json.dump(out, open(STATUS,'w'), indent=1)
    print('status.json written')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv)>1 else 'roster'
    if cmd=='seed': seed()
    elif cmd=='roster': roster()
    elif cmd=='train': train(sys.argv[2], ' '.join(sys.argv[3:-1]) if len(sys.argv)>4 else sys.argv[3], int(sys.argv[-1]) if len(sys.argv)>4 and sys.argv[-1].isdigit() else 25)
    elif cmd=='status': status()
    elif cmd=='journal':
        a = sys.argv[2]; print(open(os.path.join(EXP_DIR, a.lower()+'.md')).read() if os.path.exists(os.path.join(EXP_DIR,a.lower()+'.md')) else 'no journal')
    else: print(__doc__)
