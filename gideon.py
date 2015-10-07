import argparse
import copy
import yaml
from loader import start_client_processes

parser = argparse.ArgumentParser(description='Mighty Small CB Loader')

def run_workload(args):
    task = argsToTask(args)
    start_client_processes(task, standalone = True)

def argsToTask(args):

    bucket = args.get('bucket')
    password = args.get('password')
    active_hosts = args.get('hosts')
    ops_sec = args.get('ops')
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
           'active_hosts' : active_hosts}

    # set doc-template to this message
    msg_copy = copy.deepcopy(msg)
    msg_copy['template'] = {}
    msg_copy['template']['cc_queues'] = None
    msg_copy['template']['kv'] = msg

    return msg_copy



if __name__ == "__main__":

    ## ARGS ##
    parser.add_argument("--spec",  help="workload specification file", default=None)
    parser.add_argument("--bucket",  help="bucket", default="default")
    parser.add_argument("--password", help="password", default="")
    parser.add_argument("--ops",     help="ops per sec", default=0, type=int)
    parser.add_argument("--create",  help="percentage of creates 0-100", default=0, type=int)
    parser.add_argument("--update",  help="percentage of updates 0-100", default=0, type=int)
    parser.add_argument("--get",     help="percentage of gets 0-100", default=0, type=int)
    parser.add_argument("--miss",    help="percentage of misses 0-100", default=0, type=int)
    parser.add_argument("--expire",  help="percentage of expirations 0-100", default=0, type=int)
    parser.add_argument("--ttl",      default=15, help="document expires time to use when expirations set")
    parser.add_argument("--delete",  help="percentage of deletes 0-100", default=0, type=int)
    parser.add_argument("--template",help="predefined template to use", default="default")
    parser.add_argument("--hosts",  default=["127.0.0.1"],  nargs='+', help="couchbase hosts for use with standalone")
    parser.add_argument("--padding",  default="", help="you can put a custom string here when using standalone loader")
    parser.add_argument("--name",    help="predefind workload", default="default")

    args = parser.parse_args()
    args = vars(args)

    spec_file = args.get('spec']
    if spec_file:
        stream = open(spec_file, "r")
        spec = yaml.load(stream)

        # override args
        for opt in spec:
            args[opt] = spec[opt]

    run_workload(args)

