import os.path

if not os.path.exists('data'):
	os.makedirs('data')

with open('data/users.txt', 'w') as f:
	f.write('{}')
with open('data/recents.txt', 'w') as f:
	f.write('[]')
with open('data/corrects.txt', 'w') as f:
	f.write('[]')
with open('data/diffs.txt', 'w') as f:
	f.write('[' + ', '.join(['0'] * 20000) + ']')
with open('data/rated.txt', 'w') as f:
	f.write('[' + ', '.join(['0'] * 20000) + ']')
