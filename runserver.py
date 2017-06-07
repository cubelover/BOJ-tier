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
	if u not in users:
		return ''
	t = time.time()
	r = list((x[0], delta_to_str(t - x[1]), ' class="correct"' if flask.session.get('id', '') in users and is_correct(users[flask.session.get('id', '')], x[0]) else '') for x in recents[users[u]][:20])
	return flask.render_template('user.html', me = flask.session.get('id', ''), u = u, t = tiers[users[u]], r = r).replace('\n', '')

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
	if u not in users:
		return ''
	x = users[u]
	y = tiers[x]
	z = math.expm1(y / 2280) / 100
	ay = math.log1p(z * 4 / 5) * 13 / 6
	by = math.log1p(z) * 13 / 6
	cy = math.log1p(z * 5 / 4) * 13 / 6
	dy = 0
	return flask.render_template('recommend.html',
		me = flask.session.get('id', ''),
		u = u, t = y,
		ay = ay, a = _recommend(x, ay),
		by = by, b = _recommend(x, by),
		cy = cy, c = _recommend(x, cy),
		dy = dy, d = _recommend(x, dy)
	).replace('\n', '')

########
# Api

@app.route('/api/user_tp/')
def api_user_tp():
	data = flask.request.get_json(False, True)
	return flask.jsonify([(tiers[users[u]] if u in users else 0) for u in ([] if data is None else data)])

@app.route('/api/prob_tp/')
def api_prob_tp():
	data = flask.request.get_json(False, True)
	return flask.jsonify([diffs.get(p, 0) * 13 / 6 for p in ([] if data is None else data)])

########
# Data

def is_correct(x, p):
	return (p in corrects[x])

def add_user(u):
	if u not in users:
		users[u] = len(users)
		recents.append(list())
		corrects.append(set())
		tiers.append(0)

def del_user(u):
	if u in users:
		x = users.pop(u)
		recents[x] = list()
		corrects[x] = set()
		tiers[x] = 0

def add_correct(x, p):
	corrects[x].add(p)

def add_recent(x, p, t):
	if not is_correct(x, p):
		add_correct(x, p)
		recents[x].insert(0, (p, t))

def import_data():
	global users, recents, corrects, diffs, tiers
	with open('data/users.txt', 'r') as f:
		users = json.loads(f.read())
	with open('data/recents.txt', 'r') as f:
		recents = json.loads(f.read())
	with open('data/corrects.txt', 'r') as f:
		corrects = list(map(set, json.loads(f.read())))
	with open('data/diffs.txt', 'r') as f:
		diffs = json.loads(f.read())
	tiers = [0 for _ in range(len(users))]

def export_data():
	with open('data/users.txt', 'w') as f:
		f.write(json.dumps(users))
	with open('data/recents.txt', 'w') as f:
		f.write(json.dumps(recents))
	with open('data/corrects.txt', 'w') as f:
		f.write(json.dumps(list(map(list, corrects))))
	with open('data/diffs.txt', 'w') as f:
		f.write(json.dumps(diffs))

########
# Back

def observe_ranking():
	p = 1
	while alive:
		try:
			r = s.get('https://www.acmicpc.net/ranklist/%d' % p, timeout = 5).content.split(b'<a href="/user/')
			n = len(r)
			if n == 1:
				p = 1
				print('observe ranking - finished')
				continue
			p += 1
			for i in range(1, n):
				t = r[i]
				u = t[:t.index(b'"')].decode('utf-8')
				lock.acquire()
				add_user(u)
				lock.release()
		except Exception as e:
			traceback.print_tb(e.__traceback__)
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
			traceback.print_tb(e.__traceback__)
		time.sleep(1)

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
				print(u, plus, minus)
		except ValueError as e:
			lock.acquire()
			print('observe user (%s) - delete user' % u)
			del_user(u)
			lock.release()
		except Exception as e:
			print('observe user (%s) - ' % u, e)
			traceback.print_tb(e.__traceback__)

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
		print('observe user - finished')

def calculate_tier():
	global diffs, order
	diffs_tmp = [0 for _ in range(20000)]
	while alive:
		for i in range(len(users)):
			lock.acquire()
			x = list(corrects[i])
			lock.release()
			z = [math.expm1(diffs[y]) for y in x]
			z.sort()
			r = 0
			for t in z:
				r = r * .99 + t
			tiers[i] = math.log1p(r) * 2280
			for y in x:
				diffs_tmp[y] += 1 / r
		order_tmp = []
		for i in range(20000):
			diffs[i] = math.log1p(1 / diffs_tmp[i] ** .5) if diffs_tmp[i] else 1
			if diffs_tmp[i]:
				order_tmp.append((diffs[i] * 13 / 6, i))
			diffs_tmp[i] = 0
		order = sorted(order_tmp)

def autosave_data():
	while alive:
		try:
			export_data()
		except Exception as e:
			traceback.print_tb(e.__traceback__)
		time.sleep(60)

s = requests.session()

lock = threading.Lock()
th = list()
th.append((threading.Thread(target = observe_ranking, daemon = True), True))
th.append((threading.Thread(target = observe_status, daemon = True), True))
th.append((threading.Thread(target = observe_user, daemon = True), True))
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

