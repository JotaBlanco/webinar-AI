import os
base = '/Users/javiquix/Desktop/quixdev/webinar-AI'
agent = os.path.join(base, 'module-1', 'agent-08')
for name in ('data', 'code'):
    link = os.path.join(agent, name)
    target = os.path.join(base, name)
    if not os.path.lexists(link):
        os.symlink(target, link)
print(os.listdir(agent))
