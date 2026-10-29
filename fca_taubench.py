"""Formal concept analysis of the write calls in the tau-bench airline trajectories.

Reproduces the numbers of online Appendix F: the formal context, its canonical
basis, the nine policy rules checked against the context, and the classification
of the basis implications that the rules do not entail.

Usage: python fca_taubench.py TRAJECTORY_DIR DATABASE_DIR

TRAJECTORY_DIR holds gpt-4o-airline.json and sonnet-35-new-airline.json from
historical_trajectories/ of https://github.com/sierra-research/tau-bench;
DATABASE_DIR holds flights.json, reservations.json, and users.json from
tau_bench/envs/airline/data/ of the same repository.
"""
import ast
import json
import re
import sys
from datetime import datetime

FILES = ['gpt-4o-airline.json', 'sonnet-35-new-airline.json']
NOW = datetime(2024, 5, 15, 15, 0, 0)          # current time stated by the policy
WRITES = {'book_reservation': 'book', 'cancel_reservation': 'cancel',
          'update_reservation_flights': 'upd_flights',
          'update_reservation_baggages': 'upd_bags',
          'update_reservation_passengers': 'upd_pax',
          'send_certificate': 'certificate'}
CABIN = {'basic_economy': 'basic', 'economy': 'economy', 'business': 'business'}
YES = re.compile(r'\b(yes|yeah|yep|yup|oui|proceed|go ahead|confirm\w*)\b', re.I)
ACTIONS = ['book', 'cancel', 'upd_flights', 'upd_bags', 'upd_pax', 'certificate']
STATE = ['regular', 'silver', 'gold', 'basic', 'economy', 'business',
         'insured', 'uninsured', 'recent', 'old', 'flown']
ATTRIBUTES = ACTIONS + ['confirmed', 'user_read', 'res_read'] + STATE + [
    'cabin_changed', 'flights_changed', 'bags_removed', 'pay_ok', 'pay_in_profile']

# Rules of the policy: (premise, conclusion); conclusion None forbids the premise.
RULES = {
    'W1': [([a], ['confirmed']) for a in ACTIONS],
    'W2': [(['upd_flights', 'basic', 'flights_changed'], None)],
    'W3': [(['cancel', 'old', 'uninsured'], ['business'])],
    'W4': [(['cancel', 'flown'], None)],
    'W5': [(['upd_bags', 'bags_removed'], None)],
    'W6': [(['book'], ['user_read']), (['book'], ['pay_in_profile'])],
    'W7': [(['book'], ['pay_ok'])],
    'W8': [([a], ['res_read']) for a in ['cancel', 'upd_flights', 'upd_bags', 'upd_pax']],
    'W9': [(['certificate', 'regular', 'uninsured'], ['business'])],
}


def calls_of(message):
    tc = message.get('tool_calls')
    if not tc or tc == 'None':
        return []
    tc = tc if isinstance(tc, list) else ast.literal_eval(tc)
    out = []
    for c in tc:
        args = c['function']['arguments']
        out.append((c.get('id'), c['function']['name'],
                    json.loads(args) if isinstance(args, str) else args))
    return out


def parse(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def build_context(traj_dir, db_dir):
    """One object per write call, with its attributes and markers.

    Markers are not attributes: success (reward 1), ref (same tool and same
    reservation or user as an action of the reference solution), and disrupted
    (a flight of the reservation was cancelled by the airline)."""
    flights = json.load(open(db_dir + '/flights.json'))
    reservations = json.load(open(db_dir + '/reservations.json'))
    users = json.load(open(db_dir + '/users.json'))

    def status(segment):
        return flights.get(segment['flight_number'], {}).get('dates', {}) \
            .get(segment['date'], {}).get('status')

    objects, episodes = [], []
    for name in FILES:
        for ep in json.load(open(traj_dir + '/' + name)):
            episodes.append(ep)
            state = {}                   # reservation id -> record as of the last tool output
            read_users, read_res, read_order = set(), set(), []
            by_id, last_user = {}, ''
            for m in ep['traj']:
                if m['role'] == 'user':
                    last_user = m['content'] or ''
                    continue
                if m['role'] == 'tool':
                    call, out = by_id.get(m.get('tool_call_id')), parse(m['content'])
                    if call and isinstance(out, dict):
                        if call[0] == 'get_user_details':
                            read_users.add(call[1].get('user_id'))
                        if 'reservation_id' in out and 'flights' in out:
                            state[out['reservation_id']] = out
                            if call[0] == 'get_reservation_details':
                                read_res.add(out['reservation_id'])
                                read_order.append(out['reservation_id'])
                    continue
                for cid, tool, args in calls_of(m):
                    by_id[cid] = (tool, args)
                    if tool not in WRITES:
                        continue
                    act = WRITES[tool]
                    A, marks = {act}, set()
                    if YES.search(last_user):
                        A.add('confirmed')
                    rid = args.get('reservation_id')
                    if act == 'certificate':     # the user's reservation read last
                        mine = [r for r in read_order
                                if reservations.get(r, state.get(r, {})).get('user_id') == args['user_id']]
                        rid = mine[-1] if mine else None
                    res = (state.get(rid) or reservations.get(rid)) if rid else None
                    uid = args.get('user_id') or (res or {}).get('user_id')
                    if uid in read_users:
                        A.add('user_read')
                    if uid in users:
                        A.add(users[uid]['membership'])
                    if rid and rid in read_res:
                        A.add('res_read')
                    if res:
                        A.add(CABIN[res['cabin']])
                        A.add('insured' if res.get('insurance') == 'yes' else 'uninsured')
                        age = (NOW - datetime.fromisoformat(res['created_at'])).total_seconds()
                        A.add('recent' if age <= 86400 else 'old')
                        st = [status(x) for x in res['flights']]
                        if any(s in ('landed', 'flying') for s in st):
                            A.add('flown')
                        if 'cancelled' in st:
                            marks.add('disrupted')
                        if act == 'upd_bags' and args['total_baggages'] < res['total_baggages']:
                            A.add('bags_removed')
                        if act == 'upd_flights':
                            if args.get('cabin') != res['cabin']:
                                A.add('cabin_changed')
                            old = sorted((x['flight_number'], x['date']) for x in res['flights'])
                            new = sorted((x['flight_number'], x['date']) for x in args.get('flights', []))
                            if old != new:
                                A.add('flights_changed')
                    if act == 'book':
                        A.add(CABIN[args['cabin']])
                        A.add('insured' if args.get('insurance') == 'yes' else 'uninsured')
                        pay = [p['payment_id'] for p in args.get('payment_methods', [])]
                        kinds = [p.split('_')[0] for p in pay]
                        if kinds.count('certificate') <= 1 and kinds.count('credit') <= 1 \
                                and kinds.count('gift') <= 3:
                            A.add('pay_ok')
                        profile = users.get(uid, {}).get('payment_methods', {})
                        if pay and all(p in profile for p in pay):
                            A.add('pay_in_profile')
                    if ep['reward'] == 1.0:
                        marks.add('success')
                    key = 'reservation_id' if args.get('reservation_id') else 'user_id'
                    if any(g['name'] == tool and g['kwargs'].get(key) == args.get(key)
                           for g in ep['info']['task']['actions']):
                        marks.add('ref')
                    objects.append({'model': name.split('-airline')[0], 'task': ep['task_id'],
                                    'trial': ep['trial'], 'tool': tool, 'args': args,
                                    'attrs': frozenset(A), 'marks': marks})
    return objects, episodes


def canonical_basis(objects, attributes):
    """Canonical (Duquenne-Guigues) basis by NextClosure; returns (premise, closure, support)."""
    M = list(attributes)
    pos = {a: i for i, a in enumerate(M)}
    full = (1 << len(objects)) - 1
    ext = {a: sum(1 << i for i, g in enumerate(objects) if a in g) for a in M}
    ALL = frozenset(M)

    def extent(A):
        e = full
        for a in A:
            e &= ext[a]
        return e

    def closure(A):
        e = extent(A)
        return ALL if not e else frozenset(a for a in M if ext[a] & e == e)

    def lclose(X, L):
        X, changed = set(X), True
        while changed:
            changed = False
            for P, C in L:
                if P < X and not C <= X:
                    X |= C
                    changed = True
        return frozenset(X)

    L, A = [], frozenset()
    while True:
        C = closure(A)
        if C != A:
            L.append((A, C))
        if A == ALL:
            break
        nxt = None
        for i in range(len(M) - 1, -1, -1):
            m = M[i]
            if m in A:
                A = A - {m}
            else:
                B = lclose(A | {m}, L)
                if not any(pos[x] < i for x in B - A):
                    nxt = B
                    break
        if nxt is None:
            break
        A = nxt
    return [(P, C, bin(extent(P)).count('1')) for P, C in L]


def holds(premise, conclusion, implications):
    X, changed = set(premise), True
    while changed:
        changed = False
        for P, C in implications:
            if P <= X and not C <= X:
                X |= C
                changed = True
    return conclusion <= X


def main(traj_dir, db_dir):
    objects, episodes = build_context(traj_dir, db_dir)
    ALL = frozenset(ATTRIBUTES)
    success = [o for o in objects if 'success' in o['marks']]
    print('episodes %d, successful %d; writes %d, in successful episodes %d; attributes %d'
          % (len(episodes), sum(e['reward'] == 1.0 for e in episodes), len(objects),
             len(success), len(ATTRIBUTES)))

    basis = canonical_basis([o['attrs'] for o in objects], ATTRIBUTES)
    supported = [(P, C, s) for P, C, s in basis if s > 0]
    print('canonical basis: %d implications, %d with a premise that some write satisfies'
          % (len(basis), len(supported)))

    # nine rules against the context
    def breaks(g, premise, conclusion):
        return set(premise) <= g and (conclusion is None or not set(conclusion) <= g)

    print('\nrule  premise  exceptions  failed  successful')
    broken = set()
    for rid, rules in RULES.items():
        prem = [i for i, o in enumerate(objects) if any(set(P) <= o['attrs'] for P, _ in rules)]
        exc = [i for i in prem if any(breaks(objects[i]['attrs'], P, Q) for P, Q in rules)]
        broken |= set(exc)
        n_succ = sum(1 for i in exc if 'success' in objects[i]['marks'])
        print('%-4s  %7d  %10d  %6d  %10d' % (rid, len(prem), len(exc), len(exc) - n_succ, n_succ))
    b = [o for i, o in enumerate(objects) if i in broken]
    r = [o for i, o in enumerate(objects) if i not in broken]
    fail = lambda xs: sum(1 for o in xs if 'success' not in o['marks'])
    print('writes breaking a rule: %d, %.0f%% in failed episodes; other writes: %d, %.0f%% in failed episodes'
          % (len(b), 100 * fail(b) / len(b), len(r), 100 * fail(r) / len(r)))
    print('disrupted reservations in the premise of W3:',
          sum(1 for o in objects if 'disrupted' in o['marks'] and {'cancel', 'old', 'uninsured'} <= o['attrs']))

    # rules entailed by the basis of the writes in successful episodes
    sbasis = [(P, C) for P, C, _ in canonical_basis([o['attrs'] for o in success], ATTRIBUTES)]
    entailed = [rid for rid, rules in RULES.items()
                if all(holds(frozenset(P), ALL if Q is None else frozenset(Q), sbasis) for P, Q in rules)]
    vacuous = [rid for rid, rules in RULES.items()
               if not any(set(P) <= o['attrs'] for o in success for P, _ in rules)]
    print('\nbasis of successful episodes: %d implications; entails %s (vacuously %s)'
          % (len(sbasis), ', '.join(entailed), ', '.join(vacuous)))

    # exceptions in successful episodes that the reference solution itself performs
    for rid in ('W3', 'W4'):
        exc = [o for o in success if any(breaks(o['attrs'], P, Q) for P, Q in RULES[rid])]
        print('%s exceptions in successful episodes: %d, reference actions %d, tasks %s'
              % (rid, len(exc), sum(1 for o in exc if 'ref' in o['marks']),
                 sorted({o['task'] for o in exc})))
    target = {(o['task'], o['args']['reservation_id']) for o in success
              if 'ref' in o['marks'] and o['tool'] == 'cancel_reservation'
              and any(breaks(o['attrs'], P, Q) for w in ('W3', 'W4') for P, Q in RULES[w])}
    tasks = {t for t, _ in target}
    done, not_done = [], []
    for ep in episodes:
        if ep['task_id'] not in tasks:
            continue
        rids = {rid for t, rid in target if t == ep['task_id']}
        cancelled = any(tool == 'cancel_reservation' and args.get('reservation_id') in rids
                        for m in ep['traj'] if m['role'] == 'assistant'
                        for _, tool, args in calls_of(m))
        (done if cancelled else not_done).append(ep['reward'] == 1.0)
    print('episodes of tasks %s: with the cancellation %d (%d successful), without it %d (%d successful)'
          % (sorted(tasks), len(done), sum(done), len(not_done), sum(not_done)))

    # basis implications that the rules and background knowledge do not entail
    background = []
    for group in (ACTIONS, ['basic', 'economy', 'business'], ['insured', 'uninsured'],
                  ['recent', 'old'], ['regular', 'silver', 'gold']):
        for i, a in enumerate(group):
            for c in group[i + 1:]:
                background.append((frozenset([a, c]), ALL))
    for a, c in [('cabin_changed', 'upd_flights'), ('flights_changed', 'upd_flights'),
                 ('bags_removed', 'upd_bags'), ('pay_ok', 'book'), ('pay_in_profile', 'book')]:
        background.append((frozenset([a]), frozenset([a, c])))
    for a in ['recent', 'old', 'flown', 'res_read']:
        background.append((frozenset(['book', a]), ALL))
    written = [(frozenset(P), ALL if Q is None else frozenset(P) | frozenset(Q))
               for rules in RULES.values() for P, Q in rules]
    other = [(P, C - P, s) for P, C, s in supported if not holds(P, C, background + written)]
    state_only = [x for x in other if x[1] <= set(STATE)]
    behaviour = [x for x in other if not x[1] <= set(STATE)]
    conditional = [x for x in behaviour if x[0] & set(STATE)]
    print('\nsupported implications entailed by the rules and background knowledge: %d; others: %d'
          % (len(supported) - len(other), len(other)))
    print('  concluding only facts about users and reservations: %d' % len(state_only))
    print('  concluding agent behaviour: %d, of which %d with such a fact in the premise'
          % (len(behaviour), len(conditional)))
    for P, Q, s in sorted(state_only, key=lambda x: -x[2])[:3] + \
            [x for x in behaviour if x not in conditional]:
        print('    %4d  %s -> %s' % (s, ', '.join(sorted(P)), ', '.join(sorted(Q))))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
