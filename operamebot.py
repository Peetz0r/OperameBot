#!/bin/env python3

import MySQLdb, irc.client, ssl, configparser, datetime, logging

logging.basicConfig(
  handlers=(
    logging.FileHandler(filename=datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S.log')),
    logging.StreamHandler(),
  ),
  format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
  level=logging.DEBUG,
)
logger = logging.getLogger('OperameBot')

config = configparser.ConfigParser()
t = (config.read('config.ini'), config.sections())
logger.info(f"Reading config file {t[0][0]} with scetions {t[1]}")

db = MySQLdb.connect(host=config['db']['host'], user=config['db']['user'], password=config['db']['pass'], db=config['db']['db'])
db.autocommit(True)
c = db.cursor()
logger.info(f"connected to database (host={config['db']['host']}, user={config['db']['user']}, password=not logged, db={config['db']['db']})")

date_upd_last = datetime.datetime(1, 1, 1)

def on_connect(connection, event):
  logger.info(f"connected {(event.type, event.source, event.target, event.arguments)}")
  connection.join(config['irc']['channel'])
  return

def on_join(connection, event):
  logger.info(f"joined {(event.type, event.source, event.target, event.arguments)}")
  c.execute(f'''
    SELECT o.id_order, o.total_paid, o.date_add, o.date_upd, c.name
    FROM {config['db']['prefix']}orders AS o
    LEFT JOIN {config['db']['prefix']}carrier AS c          # implicit join wouldn't show virtual orders
    ON o.id_carrier = c.id_carrier
    WHERE o.current_state = 2                               # 2 is 'Payment Accepted'
    ORDER BY o.date_upd DESC
    LIMIT 1
  ''')
  r = c.fetchone()
  global date_upd_last
  date_upd_last = r[3]
  kind = (r[4] or 'Donatie').split()[-1]
  line = f"Laatste bestelling: #{r[0]} van €{r[1]:.2f} ({kind}) geplaatst op {r[2].strftime('%Y-%m-%d %X')}"
  logger.info(line)
  connection.privmsg(config['irc']['channel'], line)
  bot.execute_every(10, checkshop, (connection,))

def on_disconnect(connection, event):
    raise SystemExit()

def checkshop(connection):
  global date_upd_last
  c.execute(f'''
    SELECT o.id_order, o.total_paid, o.date_add, o.date_upd, c.name
    FROM {config['db']['prefix']}orders AS o
    LEFT JOIN {config['db']['prefix']}carrier AS c          # implicit join wouldn't show virtual orders
    ON o.id_carrier = c.id_carrier
    WHERE o.current_state = 2                               # 2 is 'Payment Accepted'
    AND o.date_upd > %s
    ORDER BY o.date_upd ASC
    LIMIT 1
  ''', (date_upd_last,))
  r = c.fetchone()
  logger.debug(r)
  if(r is not None):
    date_upd_last = r[3]
    kind = (r[4] or 'Donatie').split()[-1]
    line = f"Nieuwe bestelling: #{r[0]} van €{r[1]:.2f} ({kind}) geplaatst op {r[2].strftime('%Y-%m-%d %X')}"
    logger.info(line)
    connection.privmsg(config['irc']['channel'], line)


client = irc.client.IRC()

try:
  if config['irc'].getboolean('ssl'):
    logger.info(f"connecting to {config['irc']['host']}:{config['irc']['port']} with SSL... ")
    ssl_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
    bot = client.server().connect(config['irc']['host'], int(config['irc']['port']), config['irc']['nick'], connect_factory=ssl_factory)
  else:
    logger.info(f"connecting to {config['irc']['host']}:{config['irc']['port']} without SSL... ")
    bot = client.server().connect(config['irc']['host'], int(config['irc']['port']), config['irc']['nick'])
except irc.client.ServerConnectionError:
  logger.error(sys.exc_info()[1])
  print(sys.exc_info()[1])
  raise SystemExit(1)

bot.add_global_handler("welcome", on_connect)
bot.add_global_handler("join", on_join)
bot.add_global_handler("disconnect", on_disconnect)

client.process_forever()
