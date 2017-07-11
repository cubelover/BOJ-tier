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

import flask, requests, threading, time, json, math, random, traceback, bisect
import settings

app = flask.Flask(__name__)

########
# Front

def delta_to_str(d):
	return '방금 전' if d < 60 else '%d분 전' % (d // 60) if d < 3600 else '%d시간 전' % (d // 3600) if d < 86400 else '%d일 전' % (d // 86400)

@app.route('/')
def index():
	return flask.render_template('index.html', me = flask.session.get('id', '')).replace('\n', '')

@app.route('/user/<u>/')
def user(u):
	lock.acquire()
	if u not in users:
		lock.release()
		return ''
	me = flask.session.get('id', '')
	t = time.time()
	r = list((x[0], delta_to_str(t - x[1]), ' class="correct"' if me in users and is_correct(users[flask.session.get('id', '')], x[0]) else '') for x in recents[users[u]][:20])
	t = tiers[users[u]]
	lock.release()
	return flask.render_template('user.html', me = me, u = u, t = t, r = r).replace('\n', '')

@app.route('/login/', methods = ['GET', 'POST'])
def login():
	if flask.request.method == 'POST':
		flask.session['id'] = flask.request.form.get('id', '')
		return flask.redirect(flask.url_for('index'))
	return flask.render_template('login.html', me = flask.session.get('id', '')).replace('\n', '')

def _recommend(user, diff):
	lock.acquire()
	j = bisect.bisect(order, (diff, ''))
	i = j - 1
	r = list()
	while len(r) < 20:
		if j == len(order) or (i >= 0 and abs(diff - order[i][0]) < abs(diff - order[j][0])):
			if not is_correct(user, order[i][1]):
				r.insert(0, (order[i][1], order[i][0]))
			i -= 1
		else:
			if not is_correct(user, order[j][1]):
				r.append((order[j][1], order[j][0]))
			j += 1
	lock.release()
	return r

@app.route('/recommend/')
def recommend():
	u = flask.session.get('id', '')
	if not u:
		return flask.redirect(flask.url_for('login'))
	lock.acquire()
	if u not in users:
		lock.release()
		return ''
	lock.release()
	x = users[u]
	y = tiers[x]
	z = math.expm1(y / 194) / 500
	ay = math.log1p(z * 4) * 1608
	by = math.log1p(z * 5) * 1608
	cy = math.log1p(z * 25 / 4) * 1608
	dy = 0
	return flask.render_template('recommend.html',
		me = flask.session.get('id', ''),
		u = u, t = y,
		ay = ay, a = _recommend(x, ay),
		by = by, b = _recommend(x, by),
		cy = cy, c = _recommend(x, cy),
		dy = dy, d = _recommend(x, dy)
	).replace('\n', '')

@app.route('/ranking/<p>/')
def ranking(p):
	try:
		p = int(p) * 100
	except:
		p = 0
	lock.acquire()
	t = rankings[p:p+100]
	lock.release()
	return flask.render_template('ranking.html', t = [(p + i + 1, t[i][1], -t[i][0]) for i in range(len(t))]).replace('\n', '')

@app.route('/problem/<p>/')
def problem(p):
	u = flask.session.get('id', '')
	if u:
		lock.acquire()
		if u in users:
			s = set(corrects[users[u]])
		else:
			s = set()
		lock.release()
	else:
		s = set()
	try:
		p = int(p)
		if p < 0 or p > 99:
			p = 0
	except:
		p = 0
	lock.acquire()
	i = bisect.bisect(order, (p * 100, -1))
	j = bisect.bisect(order, (p * 100 + 100, -1))
	t = order[i:j]
	lock.release()
	x = list()
	y = list()
	for q, r in t:
		(y if r in s else x).append((r, q))
	return flask.render_template('problem.html', x = x, y = y, p = p).replace('\n', '')

@app.route('/data/')
def data():
	lock.acquire()
	a = [(len(corrects[users[x]]), tiers[users[x]]) for x in users]
	lock.release()
	return '\n'.join(map(lambda t: str(t[0]) + ',' + str(t[1]), a))

########
# Api

@app.route('/api/user_tp/')
def api_user_tp():
	data = flask.request.get_json(False, True)
	return flask.jsonify([(tiers[users[u]] if u in users else 0) for u in (list() if data is None else data)])

@app.route('/api/prob_tp/')
def api_prob_tp():
	data = flask.request.get_json(False, True)
	return flask.jsonify([diffs.get(p, 0) * 13 / 6 for p in (list() if data is None else data)])

########
# Data

def is_correct(x, p):
	return (p in corrects[x])

def add_user(u):
	if u not in users:
		users[u] = len(corrects)
		userid.append(u)
		recents.append(list())
		corrects.append(set())
		tiers.append(0)

def del_user(u):
	if u in users:
		x = users.pop(u)
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

def add_correct(x, p):
	corrects[x].add(p)

def add_recent(x, p, t):
	if not is_correct(x, p):
		add_correct(x, p)
		recents[x].insert(0, (p, t))

def import_data():
	global users, userid, recents, corrects, diffs, rated, tiers
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
	if len(users) != len(recents) or len(users) != len(corrects):
		print('count of users, recents, users or corrects is different')
		exit(0)
	if len(diffs) != 20000 or len(rated) != 20000:
		print('count of diffs or rated is not 20000')
		exit(0)
	tiers = [0 for _ in range(len(users))]
	userid = ['' for _ in range(len(users))]
	for x, y in users.items():
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

def Error(s, e):
	print('>>> %s - ' % s, e)
	traceback.print_tb(e.__traceback__)
	print('<<<')

def observe_ranking():
	p = 1
	while alive:
		try:
			r = s.get('https://www.acmicpc.net/ranklist/%d' % p, timeout = 5).content.split(b'<a href="/user/')
			n = len(r)
			if n == 1:
				p = 1
				print('-!- observe ranking - finished')
				continue
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
			r = s.get('https://www.acmicpc.net/status/?result_id=4', timeout = 5).content.split(b'<tr')
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
			r = s.get('https://www.acmicpc.net/user/%s' % u, timeout = 30).content
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
		except ValueError as e:
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
			rated[i] = r.status_code != 404 and r.content.find(b'label-warning') == -1
			if i == 19999:
				print('-!- observe prob - finished')
				i = 0
			else:
				i += 1
		except Exception as e:
			Error('observe prob', e)

def calculate_tier():
	global diffs, order, rankings
	diffs_tmp = [0 for _ in range(20000)]
	while alive:
		lock.acquire()
		users_tmp = list(users.keys())
		lock.release()
		rankings_tmp = list()
		for u in users_tmp:
			lock.acquire()
			if u not in users:
				lock.release()
				continue
			x = [y for y in corrects[users[u]] if rated[y]]
			lock.release()
			z = [math.expm1(diffs[y]) for y in x]
			z.sort()
			r = 0
			for t in z:
				r = r * .99 + t
			r /= 5
			lock.acquire()
			if u not in users:
				lock.release()
				continue
			tiers[users[u]] = int(math.log1p(5 * r) * 194)
			rankings_tmp.append((-tiers[users[u]], u))
			lock.release()
			if not r:
				continue
			r = 1 / r
			for y in x:
				diffs_tmp[y] += r
		rankings_tmp.sort()
		lock.acquire()
		rankings = rankings_tmp
		lock.release()
		order_tmp = list()
		for i in range(20000):
			diffs[i] = math.log1p(5 / diffs_tmp[i] ** .5) if diffs_tmp[i] else 1
			if diffs_tmp[i]:
				order_tmp.append((int(diffs[i] * 1608), i))
			diffs_tmp[i] = 0
		order_tmp.sort()
		lock.acquire()
		order = order_tmp
		lock.release()

def autosave_data():
	while alive:
		export_data()
		time.sleep(60)

s = requests.session()

lock = threading.Lock()

th = list()
th.append((threading.Thread(target = observe_ranking, daemon = True), True))
th.append((threading.Thread(target = observe_status, daemon = True), True))
th.append((threading.Thread(target = observe_user, daemon = True), True))
th.append((threading.Thread(target = observe_prob, daemon = True), True))
th.append((threading.Thread(target = calculate_tier, daemon = True), True))
th.append((threading.Thread(target = autosave_data, daemon = True), False))

print('Importing data...')
import_data()

print('Starting threads...')
alive = True
for t, f in th:
	t.start()

if settings.secret_key == 'qOBJEdA3VfGpaq992oe4':
	print('-*- Please change settings.secret_key! ex) %s' % ''.join(random.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz') for _ in range(20)))
app.secret_key = settings.secret_key
app.run('localhost', 5000)

print('Waiting for threads to die...')
alive = False
for t, f in th:
	if f:
		t.join()

print('Exporting data...')
export_data()

