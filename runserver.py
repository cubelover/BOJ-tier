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

import flask, requests, threading, time, json

app = flask.Flask(__name__)

########
# Front

def delta_to_str(d):
	return '방금 전' if d < 60 else '%d분 전' % (d // 60) if d < 3600 else '%d시간 전' % (d // 3600) if d < 86400 else '%d일 전' % (d // 86400)

@app.route('/')
def index():
	return flask.render_template('index.html').replace('\n', '')

@app.route('/user/<u>/')
def user(u):
	if u not in users:
		return ''
	t = time.time()
	r = list((x[0], delta_to_str(t - x[1])) for x in recents[users[u]])
	return flask.render_template('user.html', u = u, r = r if u in users else []).replace('\n', '')

########
# Data

def is_correct(x, p):
	return (p in corrects[x])

def add_user(u):
	if u not in users:
		users[u] = len(users)
		recents.append(list())
		corrects.append(set())

def add_correct(x, p):
	corrects[x].add(p)
	solvers[p].add(x)

def add_recent(x, p, t):
	if not is_correct(x, p):
		add_correct(x, p)
		recents[x].insert(0, (p, t))
		while len(recents[x]) > 20:
			recents[x].pop()

def import_data():
	global users, recents, corrects
	with open('data/users.txt', 'r') as f:
		users = json.loads(f.read())
	with open('data/recents.txt', 'r') as f:
		recents = json.loads(f.read())
	with open('data/corrects.txt', 'r') as f:
		corrects = list(map(set, json.loads(f.read())))

def preprocess():
	global solvers
	solvers = [set() for _ in range(20000)]
	for x in range(len(users)):
		for y in corrects[x]:
			solvers[y].add(x)

def export_data():
	with open('data/users.txt', 'w') as f:
		f.write(json.dumps(users))
	with open('data/recents.txt', 'w') as f:
		f.write(json.dumps(recents))
	with open('data/corrects.txt', 'w') as f:
		f.write(json.dumps(list(map(list, corrects))))

########
# Back

def observe_ranking():
	p = 1
	while alive:
		z = 'observe ranking (%d)' % p
		try:
			r = s.get('https://www.acmicpc.net/ranklist/%d' % p, timeout = 5).content.split(b'<a href="/user/')
			n = len(r)
			if n == 1:
				p = 1
				continue
			p += 1
			for i in range(1, n):
				t = r[i]
				u = t[:t.find(b'"')].decode('utf-8')
				add_user(u)
			print(z, '-', 'success')
		except Exception as e:
			print(z, '-', e)
		time.sleep(5)

def observe_status():
	z = 'observe status'
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
				u = t[:t.find(b'"')].decode('utf-8')
				t = t[t.find(b'/problem/') + 9:]
				p = int(t[:t.find(b'"')])
				add_user(u)
				add_recent(users[u], p, T)
			print(z, '-', 'success')
		except Exception as e:
			print(z, '-', e)
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
			z = 'observe user (%d, %s)' % (len(users_tmp), u)
			lock.release()
			r = s.get('https://www.acmicpc.net/user/%s' % u, timeout = 30).content
			r = r[r.find(b'<div class = "panel-body">'):]
			r = r[:r.find(b'</div>')].split(b'<a href = "/problem/')
			n = len(r)
			corrects[users[u]] = set(int(t[:t.find(b'"')]) for t in r[1::2])
			print(z, '-', 'success')
		except Exception as e:
			lock.acquire()
			users_tmp.append(u)
			lock.release()
			print(z, '-', e)

def observe_user():
	global users_tmp
	while alive:
		users_tmp = list(users.keys())
		th = [threading.Thread(target = _observe_user, daemon = True) for _ in range(8)]
		for t in th:
			t.start()
		for t in th:
			t.join()
		print('observe status - finished')

def autosave_data():
	z = 'autosave data'
	while alive:
		try:
			export_data()
			print(z, '-', 'success')
		except Exception as e:
			print(z, '-', e)
		time.sleep(60)

s = requests.session()

lock = threading.Lock()
th = list()
th.append((threading.Thread(target = observe_ranking, daemon = True), True))
th.append((threading.Thread(target = observe_status, daemon = True), True))
th.append((threading.Thread(target = observe_user, daemon = True), True))
th.append((threading.Thread(target = autosave_data, daemon = True), False))

print('Importing data...')
import_data()

print('Preprocessing data...')
preprocess()

print('Starting threads...')
alive = True
for t, f in th:
	t.start()
app.run('localhost', 5000)

print('Waiting for threads to die...')
alive = False
for t, f in th:
	if f:
		t.join()

print('Exporting data...')
export_data()
