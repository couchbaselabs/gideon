import argparse
import copy
import yaml
from loader import start_client_processes
from query import query_loader

parser = argparse.ArgumentParser(description='Mighty Small CB Loader')
subparsers = parser.add_subparsers(help="workload type")

def run_workload(args):
    task = argsToTask(args)
    start_client_processes(task, standalone = True)

def argsToTask(args):

    bucket = args.get('bucket')
    password = args.get('password')
    user_password = args.get('user_password')
    active_hosts = args.get('hosts')
    ops_sec = args.get('ops')
    sizes = args.get('sizes')
    persist_to = args.get('persist_to')
    replicate_to = args.get('replicate_to')
    num_consumers = 1

    ops_sec = int(ops_sec)/num_consumers
    create_count = int(ops_sec *  args.get('create')/100)
    update_count = int(ops_sec *  args.get('update')/100)
    get_count = int(ops_sec *  args.get('get')/100)
    del_count = int(ops_sec *  args.get('delete')/100)
    exp_count = int(ops_sec *  args.get('expire')/100)

    ttl = args.get('ttl')
    miss_perc = args.get('miss')

    # broadcast to sdk_consumers
    msg = {'bucket' : bucket,
           'id' : bucket,
           'password' : password,
           'user_password' : user_password,
           'ops_sec' : ops_sec,
           'create_count' : create_count,
           'update_count' : update_count,
           'get_count' : get_count,
           'del_count' : del_count,
           'exp_count' : exp_count,
           'cc_queues' : None,
           'consume_queue' : None,
           'ttl' : ttl,
           'miss_perc' : miss_perc,
           'active' : True,
           'active_hosts' : active_hosts,
           'sizes': sizes,
           'persist_to': persist_to,
           'replicate_to': replicate_to}

    # set doc-template to this message
    msg_copy = copy.deepcopy(msg)
    msg_copy['template'] = {}
    msg_copy['template']['cc_queues'] = None
    msg_copy['template']['kv'] = {
        'type': 'gideon',
        'bucket': bucket,
        'active_hosts' : active_hosts,
        'ops_sec' : ops_sec,
        'sizes': sizes,
        'rating': "$flo",
        'city':  "$str",
        'state': "$str1",
        'activity': ["$str20","$str20","$str20","$str5","$str15"],
        'profile': {
             'name':  "$str10",
             'likes': "$int",
             'online': "$boo",
             'friends': ["$str","$str","$str","$str","$str"],
             'status': "$str5 $str5 $str1 $str1 $str20"
         },
        "build_id": "$int4",
        "claim": "$str40",
        "name": "$str10",
        "url": "$str20",
        "component": "$str1",
        "failCount": 0,
        "totalCount": "$int2",
        "result": "SUCCESS",
        "duration": "$int4",
        "priority": "$str1",
        "os": "$str1",
        "build": "gideon-$int1",
        "description": "$str10 $str5 $str15 $str1 $str20"
    }

    return msg_copy



def run_kv(args):
    spec_file = args.get('spec')
    if spec_file:
        stream = open(spec_file, "r")
        spec = yaml.load(stream)

        # override args
        for opt in spec:
            args[opt] = spec[opt]

    run_workload(args)


def init_kv_parser():

    kv_parser = subparsers.add_parser('kv')
    kv_parser.add_argument("--spec",  help="workload specification file", default=None)
    kv_parser.add_argument("--bucket",  help="bucket", default="default")
    kv_parser.add_argument("--password", help="password", default="")
    kv_parser.add_argument("--user_password", help="rbac user password", default="password")
    kv_parser.add_argument("--ops",     help="ops per sec", default=0, type=int)
    kv_parser.add_argument("--create",  help="percentage of creates 0-100", default=0, type=int)
    kv_parser.add_argument("--update",  help="percentage of updates 0-100", default=0, type=int)
    kv_parser.add_argument("--get",     help="percentage of gets 0-100", default=0, type=int)
    kv_parser.add_argument("--miss",    help="percentage of misses 0-100", default=0, type=int)
    kv_parser.add_argument("--expire",  help="percentage of expirations 0-100", default=0, type=int)
    kv_parser.add_argument("--ttl",      default=15, help="document expires time to use when expirations set")
    kv_parser.add_argument("--delete",  help="percentage of deletes 0-100", default=0, type=int)
    kv_parser.add_argument("--template",help="predefined template to use", default="default")
    kv_parser.add_argument("--hosts",  default=["127.0.0.1"],  nargs='+', help="couchbase hosts for use with standalone")
    kv_parser.add_argument("--padding",  default="", help="you can put a custom string here when using standalone loader")
    kv_parser.add_argument("--name",    help="predefind workload", default="default")
    kv_parser.add_argument("--sizes",  default=[128, 256], nargs="+", type=int, help="kv doc size(json)")
    kv_parser.add_argument("--persist_to", default=0, type=int, help="persist_to argument for create and update")
    kv_parser.add_argument("--replicate_to", default=0, type=int, help="replicate_to argument for create and update")
    kv_parser.set_defaults(handler=run_kv)


def run_query(args):
    query_loader(args)

def init_query_parser():
    query_parser = subparsers.add_parser('query')
    query_parser.add_argument("--host",  help="host to send query requests", default="127.0.0.1")
    query_parser.add_argument("--port",  help="couch query port", default="8092")
    query_parser.add_argument("--bucket",  help="bucket with design doc", default="default")
    query_parser.add_argument("--ddoc",  help="design doc name", default=None, required=True)
    query_parser.add_argument("--view",  help="name of view", default="default", required=True)
    query_parser.add_argument("--concurrency", help="concurrent", default=100, type=int)
    query_parser.add_argument("--params", nargs="+", help="query params key1:value1 key2:value2 ...", default=None)
    query_parser.set_defaults(handler=run_query)


if __name__ == "__main__":

    # setup cli parsers
    init_kv_parser()
    init_query_parser()

    # parse args
    args = parser.parse_args()
    dict_args = vars(args)
    args.handler(dict_args)
