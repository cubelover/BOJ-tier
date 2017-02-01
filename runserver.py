import flask, requests, threading, time, datetime

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
	t = time.time() + 32400
	r = list((x[0], delta_to_str(t - x[1])) for x in recents[users[u]])
	return flask.render_template('user.html', u = u, r = r if u in users else []).replace('\n', '')

########
# Back

def is_correct(x, p):
	return (p in corrects[x])

def add_user(u):
	users[u] = len(users)
	recents.append(list())
	corrects.append(set())

def add_correct(x, p):
	corrects[x].add(p)

def add_recent(x, p, t):
	if not is_correct(x, p):
		add_correct(x, p)
		recents[x].insert(0, (p, t))
		while len(recents[x]) > 4:
			recents[x].pop()

def observe_status(s):
	while True:
		r = s.get('https://www.acmicpc.net/status/?result_id=4').content.split(b'<tr')
		for i in range(len(r) - 1, 1, -1):
			t = r[i]
			t = t[t.find(b'/user/') + 6:]
			u = t[:t.find(b'"')].decode('utf-8')
			t = t[t.find(b'/problem/') + 9:]
			p = int(t[:t.find(b'"')])
			t = t[t.find(b'"top"') + 14:]
			t = t[:t.find(b'"')].decode('utf-8')
			t = int(time.mktime(time.strptime(t, '%Y년 %m월 %d일 %H시 %M분 %S초')))
			if u not in users:
				add_user(u)
			add_recent(users[u], p, t)
		time.sleep(1)

s = requests.session()
users = dict()
recents = list()
corrects = list()

threading.Thread(target = observe_status, args = (s, ), daemon = True).start()
app.run('localhost', 5000)

