# BOJ-tier
# Copyright (C) 2017  Jeehak Yoon
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import flask, requests, threading, time, json, math, random, traceback, bisect, logging, sys
import settings

app = flask.Flask(__name__)

def Error(s, e):
	print('>>> %s - ' % s, e)
	traceback.print_tb(e.__traceback__)
	print('<<<')

########
# Front

def delta_to_str(d):
	return '방금 전' if d < 60 else '%d분 전' % (d // 60) if d < 3600 else '%d시간 전' % (d // 3600) if d < 259200 else '%d일 전' % (d // 86400)

def render(f, **a):
	return flask.render_template(f, me = flask.session.get('id', ''), **a).replace('\n', '')

@app.route('/')
def index():
	return render('index.html')

@app.route('/tool/')
def tools():
	t = flask.request.args.get('t', '')
	if t == 'prob':
		return render('tool_prob.html')
	return render('tool.html')

@app.route('/user/<u>/')
def user(u):
	lock.acquire()
	u, x = get_user(u)
	if u is None:
		lock.release()
		return render('error.html')
	mu = flask.session.get('id', '')
	mu, mx = get_user(mu)
	t = time.time()
	r = list((_[0], delta_to_str(t - _[1]), '' if mu is None or not is_correct(mx, _[0]) else ' class="correct"', ConvDiff(diffs[_[0]])) for _ in recents[x][:20])
	t = ConvTier(tiers[x])
	o = GetRanking(x)
	lock.release()
	return render('user.html', u = u, t = t, r = r, o = o)

@app.route('/login/', methods = ['GET', 'POST'])
def login():
	if flask.request.method == 'POST':
		flask.session['id'] = flask.request.form.get('id', '').strip()
		return flask.redirect(flask.url_for('index'))
	return render('login.html')

def _recommend(user, diff):
	j = bisect.bisect(order, (diff, ''))
	i = j - 1
	r = list()
	while len(r) < 20:
		if j == len(order) or (i >= 0 and abs(diff - order[i][0]) < abs(diff - order[j][0])):
			if not is_correct(user, order[i][1]):
				r.insert(0, (order[i][1], ConvDiff(order[i][0])))
			i -= 1
		else:
			if not is_correct(user, order[j][1]):
				r.append((order[j][1], ConvDiff(order[j][0])))
			j += 1
	return r

@app.route('/recommend/')
def recommend():
	u = flask.session.get('id', '')
	if not u:
		return flask.redirect(flask.url_for('login'))
	lock.acquire()
	u, x = get_user(u)
	if u is None:
		lock.release()
		return render('error.html')
	y = tiers[x]
	z = y / 100
	ay = z * 4 / 5
	by = z
	cy = z * 5 / 4
	dy = 0
	a, b, c, d = (_recommend(x, _) for _ in (ay, by, cy, dy))
	lock.release()
	return render('recommend.html',
		u = u, t = ConvTier(y),
		ay = ConvDiff(ay), a = a,
		by = ConvDiff(by), b = b,
		cy = ConvDiff(cy), c = c,
		dy = dy, d = d)

@app.route('/ranking/<p>/')
def ranking(p):
	try:
		p = int(p) * 100
	except:
		p = 0
	lock.acquire()
	t = rankings[p:p+100]
	lock.release()
	return render('ranking.html', t = [(p + i + 1, t[i][1], ConvTier(-t[i][0])) for i in range(len(t))])

@app.route('/problem/<p>/')
def problem(p):
	u = flask.session.get('id', '')
	lock.acquire()
	if u:
		u, x = get_user(u)
		if u is None:
			s = set()
		else:
			s = set(corrects[x])
	else:
		s = set()
	lock.release()
	try:
		p = int(p)
		if p < 0 or p > 99:
			p = 0
	except:
		p = 0
	lock.acquire()
	i = bisect.bisect(order, (ConvDiff(p * 100, True), -1))
	j = bisect.bisect(order, (ConvDiff(p * 100 + 100, True), -1))
	t = order[i:j]
	lock.release()
	x = list()
	y = list()
	for q, r in t:
		(y if r in s else x).append((r, ConvDiff(q)))
	return render('problem.html', x = x, y = y, p = p)

@app.route('/problems/')
def problems():
	u = flask.session.get('id', '')
	lock.acquire()
	if u:
		u, x = get_user(u)
		if u is None:
			s = set()
		else:
			s = set(corrects[x])
	else:
		s = set()
	x = list([i, 0, 0] for i in range(100))
	d = list(order)
	lock.release()
	for q, r in d:
		x[ConvDiff(q) // 100][1 if r in s else 2] += 1
	return render('problems.html', x = x)

########
# Api

API_FAIL = json.dumps({ 'success': False, 'result': None })

def api_prob(data):
	if type(data) is not list:
		return None
	res = list()
	for prob in data:
		if type(prob) is not int:
			return None
		res.append({ 'diff': ConvDiff(diffs[prob]) / 100, 'rated': rated[prob] } if 0 <= prob < 20000 else { 'diff': 100.0, 'rated': False })
	return res

def api_user(data):
	if type(data) is not list:
		return None
	res = list()
	for u in data:
		if type(u) is not str:
			return None
		lock.acquire()
		u, x = get_user(u)
		if u is None:
			lock.release()
			res.append({ 'userid': None, 'tier': None, 'ranking': None })
			continue
		res.append({ 'userid': u, 'tier': ConvTier(tiers[x]) / 100, 'ranking': GetRanking(x) })
		lock.release()
	return res

APIS = { 'prob': api_prob, 'user': api_user }

@app.route('/api/')
def api():
	return render('api.html')

@app.route('/api/<action>', methods = ['GET', 'POST'])
def api_action(action):
	if action not in APIS:
		return API_FAIL
	if flask.request.is_json:
		data = flask.request.get_json(silent = True)
	else:
		try:
			data = json.loads(flask.request.values.get('q', ''))
		except:
			return API_FAIL
	func = APIS[action]
	res = func(data)
	return API_FAIL if res == None else json.dumps({ 'success': True, 'result': res})

########
# Data

def is_correct(x, p):
	return (p in corrects[x])

def add_user(u):
	if u not in users:
		print('-!- add user (%s)' % u)
		users[u] = len(corrects)
		userid.append(u)
		username[u.lower()] = u
		recents.append(list())
		corrects.append(set())
		tiers.append(0)

def del_user(u):
	if u in users:
		x = users.pop(u)
		username.pop(u.lower())
		y = len(users)
		users[userid[y]] = x
		userid[x] = userid[y]
		userid.pop()
		recents[x] = recents[y]
		recents.pop()
		corrects[x] = corrects[y]
		corrects.pop()
		tiers[x] = tiers[y]
		tiers.pop()

def get_user(u):
	u = u.lower()
	if u not in username:
		return (None, None)
	u = username[u]
	x = users[u]
	return (u, x)

def add_correct(x, p):
	corrects[x].add(p)

def add_recent(x, p, t):
	if not is_correct(x, p):
		add_correct(x, p)
		recents[x].insert(0, (p, t))

def import_data():
	global users, userid, username, workbooks, recents, corrects, diffs, rated, tiers
	with open('data/users.txt', 'r') as f:
		users = json.loads(f.read())
	with open('data/recents.txt', 'r') as f:
		recents = json.loads(f.read())
	with open('data/corrects.txt', 'r') as f:
		corrects = list(map(set, json.loads(f.read())))
	with open('data/diffs.txt', 'r') as f:
		diffs = json.loads(f.read())
	with open('data/rated.txt', 'r') as f:
		rated = json.loads(f.read())
	# with open('data/workbooks.txt', 'r') as f:
	#	workbooks = json.loads(f.read())
	if len(users) != len(recents) or len(users) != len(corrects):
		print('count of users, recents, users or corrects is different')
		exit(0)
	if len(diffs) != 20000 or len(rated) != 20000:
		print('count of diffs or rated is not 20000')
		exit(0)
	tiers = [0 for _ in range(len(users))]
	userid = ['' for _ in range(len(users))]
	username = dict()
	for x, y in users.items():
		z = x.lower()
		if z in username:
			print('users contains duplicate keys')
			exit(0)
		username[z] = x
		if userid[y]:
			print('users contains duplicate values')
			exit(0)
		userid[y] = x

def export_data():
	lock.acquire()
	try:
		with open('data/users.txt', 'w') as f:
			f.write(json.dumps(users))
		with open('data/recents.txt', 'w') as f:
			f.write(json.dumps(recents))
		with open('data/corrects.txt', 'w') as f:
			f.write(json.dumps(list(map(list, corrects))))
		with open('data/diffs.txt', 'w') as f:
			f.write(json.dumps(diffs))
		with open('data/rated.txt', 'w') as f:
			f.write(json.dumps(rated))
	except Exception as e:
		Error('export data', e)
	lock.release()

########
# Back

def ConvTier(x, f = False):
	return math.expm1(x / 194) / 5 if f else int(math.log1p(x * 5) * 194)

def ConvDiff(x, f = False):
	return math.expm1(x / 1608) / 5 if f else int(math.log1p(x * 5) * 1608)

def GetRanking(x):
	return bisect.bisect_left(rankings, (-tiers[x], ''))

def observe_ranking():
	p = 1
	while alive:
		try:
			r = s.get('https://www.acmicpc.net/ranklist/%d' % p, timeout = 5)
			if r.status_code == 404:
				p = 1
				print('-!- observe ranking - finished')
			elif r.status_code == 200:
				r = r.content.split(b'<a href="/user/')
				n = len(r)
				p += 1
				for i in range(1, n):
					t = r[i]
					u = t[:t.index(b'"')].decode('utf-8')
					lock.acquire()
					add_user(u)
					lock.release()
		except Exception as e:
			Error('observe ranking', e)
		time.sleep(5)

def observe_status():
	while alive:
		try:
			T = time.time()
			r = s.get('https://www.acmicpc.net/status/?result_id=4', timeout = 5)
			if r.status_code == 200:
				r = r.content.split(b'<tr')
				for i in range(21, 1, -1):
					t = r[i]
					i = t.find(b'/user/')
					if i == -1:
						continue
					t = t[i + 6:]
					u = t[:t.index(b'"')].decode('utf-8')
					t = t[t.index(b'/problem/') + 9:]
					p = int(t[:t.index(b'"')])
					lock.acquire()
					add_user(u)
					add_recent(users[u], p, T)
					lock.release()
		except Exception as e:
			Error('observe status', e)

def _observe_user():
	while alive:
		try:
			lock.acquire()
			if not users_tmp:
				lock.release()
				return
			u = users_tmp[-1]
			users_tmp.pop()
			lock.release()
			r = s.get('https://www.acmicpc.net/user/%s' % u, timeout = 30)
			if r.status_code == 200:
				r = r.content
				r = r[r.index(b'<div class = "panel-body">'):]
				r = r[:r.index(b'</div>')].split(b'<a href = "/problem/')
				tmp = set(int(t[:t.index(b'"')]) for t in r[1::2])
				lock.acquire()
				plus = tmp - corrects[users[u]]
				minus = corrects[users[u]] - tmp
				corrects[users[u]] = tmp
				lock.release()
				if plus or minus:
					print(time.strftime('[%Y-%m-%d %H:%M:%S]'), u, plus, minus)
			elif r.status_code == 404:
				lock.acquire()
				print('-!- observe user (%s) - delete user' % u)
				del_user(u)
				lock.release()
		except Exception as e:
			Error('observe user (%s)' % u, e)

def observe_user():
	global users_tmp
	while alive:
		lock.acquire()
		users_tmp = list(users.keys())
		lock.release()
		th = [threading.Thread(target = _observe_user, daemon = True) for _ in range(4)]
		for t in th:
			t.start()
		for t in th:
			t.join()
		print('-!- observe user - finished')

def observe_prob():
	i = 0
	while alive:
		try:
			r = s.get('https://www.acmicpc.net/problem/%d' % i, timeout = 5)
			if r.status_code == 200:
				rated[i] = r.content.find(b'label-warning') == -1
			elif r.status_code == 404:
				rated[i] = False
			if i == 19999:
				print('-!- observe prob - finished')
				i = 0
			else:
				i += 1
		except Exception as e:
			Error('observe prob', e)

def _calculate_tier():
	global tiers, diffs, order, rankings
	try:
		lock.acquire()
		users_tmp = list(users.keys())
		lock.release()
		diffs_tmp = [0 for _ in range(20000)]
		rankings_tmp = list()
		n = len(users_tmp)
		tiers_tmp = list()
		for i in range(n):
			u = users_tmp[i]
			lock.acquire()
			if u not in users:
				lock.release()
				tiers_tmp.append(0)
				continue
			x = [y for y in corrects[users[u]] if rated[y]]
			lock.release()
			z = [diffs[y] for y in x]
			z.sort()
			r = 0
			for t in z:
				r = r * .99 + t
			tiers_tmp.append(r)
			rankings_tmp.append((-r, u))
			if not r:
				continue
			r = 1 / r
			for y in x:
				diffs_tmp[y] += r
		rankings_tmp.sort()
		lock.acquire()
		rankings = rankings_tmp
		for i in range(n):
			u = users_tmp[i]
			if u in users:
				tiers[users[u]] = tiers_tmp[i]
		lock.release()
		order_tmp = list()
		for i in range(20000):
			diffs[i] = 1 / diffs_tmp[i] ** .5 if diffs_tmp[i] else 100.26
			if diffs_tmp[i]:
				order_tmp.append((diffs[i], i))
		order_tmp.sort()
		lock.acquire()
		order = order_tmp
		lock.release()
	except Exception as e:
		Error('calculate tier', e)

def calculate_tier():
	cnt = 0
	st = time.time()
	while alive:
		_calculate_tier()
		cnt += 1
		if cnt == 1000:
			cnt = 0
			en = time.time()
			print('-!- calculate tier - alive (%f s)' % (en - st))
			st = en

def autosave_data():
	while alive:
		export_data()
		time.sleep(60)

MAIN = len(sys.argv) == 1

s = requests.session()

lock = threading.Lock()

print('Importing data...')
import_data()

if MAIN:
	th = list()
	th.append((threading.Thread(target = observe_ranking, daemon = True), True))
	th.append((threading.Thread(target = observe_status, daemon = True), True))
	th.append((threading.Thread(target = observe_user, daemon = True), True))
	th.append((threading.Thread(target = observe_prob, daemon = True), True))
	th.append((threading.Thread(target = autosave_data, daemon = True), False))
	th.append((threading.Thread(target = calculate_tier, daemon = True), True))


	print('Starting threads...')
	alive = True
	for t, f in th:
		t.start()

	time.sleep(5)
else:
	_calculate_tier()

logging.getLogger('werkzeug').setLevel(logging.ERROR)

if settings.secret_key == 'qOBJEdA3VfGpaq992oe4':
	print('-*- Please change settings.secret_key! ex) %s' % ''.join(random.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz') for _ in range(20)))
app.secret_key = settings.secret_key
app.run('localhost', 5000 if MAIN else 8888)

if MAIN:
	print('Waiting for threads to die...')
	alive = False
	for t, f in th:
		if f:
			t.join()

	print('Exporting data...')
	export_data()

