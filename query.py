import requests
import eventlet

def _query(args):
    r = requests.get(args['url'], params=args['params'])

def query_loader(args):

    host = args.get("host")+":"+args.get("port")
    bucket = args.get("bucket")
    ddoc = args.get("ddoc")
    view = args.get("view")
    params = args.get('params')
    url_params = {}
    if params is not None:
        for p in params:
            key, value = p.split(":")
            url_params[key] = value
    url = "/".join(["http:/", host,bucket,"_design",ddoc,"_view",view])
    args = {"url": url,
            "params": url_params}

    pile = eventlet.GreenPile(10)
    while True:
        pile.spawn(_query, args)
