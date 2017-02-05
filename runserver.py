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
	users[u] = len(users)
	recents.append(list())
	corrects.append(set())

def add_correct(x, p):
	corrects[x].add(p)

def add_recent(x, p, t):
	if not is_correct(x, p):
		add_correct(x, p)
		recents[x].insert(0, (p, t))
		while len(recents[x]) > 10:
			recents[x].pop()

def import_data():
	global users, recents, corrects
	with open('data/users.txt', 'r') as f:
		users = json.loads(f.read())
	with open('data/recents.txt', 'r') as f:
		recents = json.loads(f.read())
	with open('data/corrects.txt', 'r') as f:
		corrects = list(map(set, json.loads(f.read())))

def export_data():
	with open('data/users.txt', 'w') as f:
		f.write(json.dumps(users))
	with open('data/recents.txt', 'w') as f:
		f.write(json.dumps(recents))
	with open('data/corrects.txt', 'w') as f:
		f.write(json.dumps(list(map(list, corrects))))

########
# Back

def observe_status(s):
	while alive:
		try:
			T = time.time()
			r = s.get('https://www.acmicpc.net/status/?result_id=4').content.split(b'<tr')
			for i in range(len(r) - 1, 1, -1):
				t = r[i]
				i = t.find(b'/user/')
				if i == -1:
					continue
				t = t[i + 6:]
				u = t[:t.find(b'"')].decode('utf-8')
				t = t[t.find(b'/problem/') + 9:]
				p = int(t[:t.find(b'"')])
				if u not in users:
					add_user(u)
				add_recent(users[u], p, T)
		except Exception as e:
			print(e)
		time.sleep(5)

s = requests.session()

th = list()
th.append(threading.Thread(target = observe_status, args = (s, ), daemon = True))

print('Importing data...')
import_data()
alive = True
for t in th:
	t.start()
app.run('localhost', 5000)
print('Waiting for threads to die...')
alive = False
for t in th:
	t.join()
print('Exporting data...')
export_data()
