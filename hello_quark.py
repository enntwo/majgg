from quart import Quart
from quart import render_template
from quart import redirect, request, url_for

import asyncio
import hashlib
import hmac
import logging
import random
import uuid
from optparse import OptionParser

import aiohttp
import os

from mahjong_soul_api.ms.base import MSRPCChannel
from mahjong_soul_api.ms.rpc import Lobby
import mahjong_soul_api.ms.protocol_pb2 as pb
from google.protobuf.json_format import MessageToJson

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

MS_HOST = "https://game.maj-soul.com"

app = Quart(__name__)

@app.route('/')
async def index():
    try:
        logging.info(os.environ.get("CN_ACCOUNT_NAME", default="true"))
    except Exception as e:
        logging.info("error: {0}".format(e))
    return os.environ.get("CN_ACCOUNT_NAME", default="true") # await render_template('hello.html')

@app.route('/record/', methods=['POST'])
async def record():
    form = await request.form
    # lobby, channel = await connect()
    # await login(lobby, os.environ.get('CN_ACCOUNT_NAME'), os.environ.get('CN_ACCOUNT_PASS'))

    # game_log = await load_and_process_game_log(lobby, "210110-39822d27-fa68-4315-ad33-e60074c682e1")
    # logging.info("game {} result : \n{}".format(game_log.head.uuid, game_log.head.result))

    # await channel.close()
    return form['uuid'] #await render_template('hello.html', name="test")


# @app.route('/')
# def hello_world():
#     return 'Hello, World!'

# @app.route('/hello/')
# @app.route('/hello/<name>')
# def hello(name=None):

    #lobby, channel = await connect()
    #await login(lobby, "enntwo@gmail.com", "cnservertestpass")

    #game_log = await load_and_process_game_log(lobby, "210110-39822d27-fa68-4315-ad33-e60074c682e1")
    #logging.info("game {} result : \n{}".format(game_log.head.uuid, game_log.head.result))

    #await channel.close()

#    return render_template('hello.html', name="test")

async def connect():
    async with aiohttp.ClientSession() as session:
        async with session.get("{}/1/version.json".format(MS_HOST)) as res:
            version = await res.json()
            logging.info(f"Version: {version}")

            version = version["version"]

        async with session.get("{}/1/v{}/config.json".format(MS_HOST, version)) as res:
            config = await res.json()
            logging.info(f"Config: {config}")

            url = config["ip"][0]["region_urls"][1]

        async with session.get(url + "?service=ws-gateway&protocol=ws&ssl=true") as res:
            servers = await res.json()
            logging.info(f"Available servers: {servers}")

            servers = servers["servers"]
            server = random.choice(servers)
            endpoint = "wss://{}/".format(server)

    logging.info(f"Chosen endpoint: {endpoint}")
    channel = MSRPCChannel(endpoint)

    lobby = Lobby(channel)

    await channel.connect(MS_HOST)
    logging.info("Connection was established")

    return lobby, channel


async def login(lobby, username, password):
    logging.info("Login with username and password")

    uuid_key = str(uuid.uuid1())

    req = pb.ReqLogin()
    req.account = username
    req.password = hmac.new(b"lailai", password.encode(), hashlib.sha256).hexdigest()
    req.device.is_browser = True
    req.random_key = uuid_key
    req.gen_access_token = True
    req.currency_platforms.append(2)

    res = await lobby.login(req)
    token = res.access_token
    if not token:
        logging.error("Login Error:")
        logging.error(res)
        return False

    return True


async def load_game_logs(lobby):
    logging.info("Loading game logs")

    records = []
    current = 1
    step = 30
    req = pb.ReqGameRecordList()
    req.start = current
    req.count = step
    res = await lobby.fetch_game_record_list(req)
    records.extend([r.uuid for r in res.record_list])

    return records


async def load_and_process_game_log(lobby, uuid):
    logging.info("Loading game log")

    req = pb.ReqGameRecord()
    req.game_uuid = uuid
    res = await lobby.fetch_game_record(req)

    record_wrapper = pb.Wrapper()
    record_wrapper.ParseFromString(res.data)

    game_details = pb.GameDetailRecords()
    game_details.ParseFromString(record_wrapper.data)

    game_records_count = len(game_details.records)
    logging.info("Found {} game records".format(game_records_count))

    round_record_wrapper = pb.Wrapper()
    is_show_new_round_record = False
    is_show_discard_tile = False
    is_show_deal_tile = False

    for i in range(0, game_records_count):
        round_record_wrapper.ParseFromString(game_details.records[i])

        if round_record_wrapper.name == ".lq.RecordNewRound" and not is_show_new_round_record:
            logging.info("Found record type = {}".format(round_record_wrapper.name))
            round_data = pb.RecordNewRound()
            round_data.ParseFromString(round_record_wrapper.data)
            print_data_as_json(round_data, "RecordNewRound")
            is_show_new_round_record = True

        if round_record_wrapper.name == ".lq.RecordDiscardTile" and not is_show_discard_tile:
            logging.info("Found record type = {}".format(round_record_wrapper.name))
            discard_tile = pb.RecordDiscardTile()
            discard_tile.ParseFromString(round_record_wrapper.data)
            print_data_as_json(discard_tile, "RecordDiscardTile")
            is_show_discard_tile = True

        if round_record_wrapper.name == ".lq.RecordDealTile" and not is_show_deal_tile:
            logging.info("Found record type = {}".format(round_record_wrapper.name))
            deal_tile = pb.RecordDealTile()
            deal_tile.ParseFromString(round_record_wrapper.data)
            print_data_as_json(deal_tile, "RecordDealTile")
            is_show_deal_tile = True

    return res


def print_data_as_json(data, type):
    json = MessageToJson(data)
    logging.info("{} json {}".format(type, json))

app.run()