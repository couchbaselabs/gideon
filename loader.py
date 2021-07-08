import asyncio
import copy
import functools
import re
import signal
import sys
import datetime
import time
import json
import gevent
import random
import argparse
# couchbase
# from couchbase.experimental import enable as enable_experimental
from acouchbase import cluster
from couchbase.exceptions import DocumentNotFoundException, \
                                 TemporaryFailException, TimeoutException, \
    NetworkException, AuthenticationException
# enable_experimental()
from couchbase.cluster import Cluster
from acouchbase.cluster import Cluster as ACluster
from acouchbase.cluster import get_event_loop
from couchbase.auth import PasswordAuthenticator
from couchbase.durability import Durability, ServerDurability, \
    ClientDurability, Cardinal
from couchbase.cluster import ClusterOptions
from couchbase.collection import UpsertOptions, RemoveOptions, GetOptions

import linecache
import os
import tracemalloc
# para
from couchbase_core.client import Client
from gevent import Greenlet, queue
import threading
import multiprocessing
from multiprocessing import Process, Event, queues

from gevent import monkey

monkey.patch_all()

# logging
import logging

logging.basicConfig(filename='consumer.log', level=logging.DEBUG)

# some global state
CB_CLUSTER_TAG = "default"
CLIENTSPERPROCESS = 4
PROCSPERTASK = 4
MAXPROCESSES = 8
PROCSSES = {}

class SDKClientAsync(object):
    @classmethod
    async def create(cls, task, task_name, task_num):
        self = SDKClientAsync(task, task_name, task_num)
        await self.create_couchbase()
        logging.info("[Thread %s] started for workload: %s" % (
        self.name, task['id']))
        return self

    def __init__(self,task, task_name, task_num):
        self.name = task_name
        self.task_num = task_num
        self.i = 0
        self.op_factor = CLIENTSPERPROCESS * PROCSPERTASK
        self.ops_sec = task['ops_sec']
        self.bucket = task['bucket']
        self.password = task['password']
        self.user_password = task['user_password']
        self.template = task['template']
        self.default_tsizes = task['sizes']
        self.create_count = int(task['create_count'] / self.op_factor)
        self.update_count = int(task['update_count'] / self.op_factor)
        self.get_count = int(task['get_count'] / self.op_factor)
        self.del_count = int(task['del_count'] / self.op_factor)
        self.exp_count = int(task['exp_count'] / self.op_factor)
        self.ttl = task['ttl']
        self.persist_to = task['persist_to']
        self.replicate_to = task['replicate_to']
        self.durability = task['durability']
        self.miss_perc = task['miss_perc']
        self.active_hosts = task['active_hosts']
        self.batch_size = 100
        self.memq = asyncio.Queue()
        self.consume_queue = task['consume_queue']
        self.standalone = task['standalone']
        self.ccq = None
        self.hotkey_batches = []
        if self.durability== None:
            self.durability_level=Durability.NONE
        elif self.durability== 'majority':
            self.durability_level=Durability.MAJORITY
        elif self.durability == 'majority_and_persist_on_master':
            self.durability_level=Durability.MAJORITY_AND_PERSIST_ON_MASTER
        elif self.durability == 'persist_to_majority':
            self.durability_level=Durability.PERSIST_TO_MAJORITY

        if self.ttl:
            self.ttl = int(self.ttl)

        if self.batch_size > self.create_count:
            self.batch_size = self.create_count

        self.active_hosts = task['active_hosts']
        self.cb = None
        self.cbs = []
        self.templates = []
        self.collections = task['collections']


    async def create_couchbase(self):
        try:
            auth = PasswordAuthenticator(self.bucket, self.user_password)
            endpoint = 'couchbase://{0}'.format(self.active_hosts[0])
            options = ClusterOptions(authenticator=auth)
            cluster = ACluster(endpoint, options=options)
            bucket = cluster.bucket(self.bucket)
            b = cluster.bucket(self.bucket)

            await bucket.on_connect()
            for scope, _collections in self.collections.items():
                for collection in _collections:
                    template = copy.deepcopy(self.template)
                    template['kv']['scope'] = scope
                    template['kv']["collection"] = collection
                    self.templates.append(template)
                    if collection == 'default':
                        cb = bucket.default_collection()
                    else:
                        cb = bucket.scope(scope).collection(collection)
                    self.cbs.append(cb)

        except Exception as ex:
            logging.error('Error trying to create CBS')
            logging.error(ex)

    async def run(self):
        try:
            cycle = ops_total = 0
            t = time.perf_counter()
            while True:
                start = datetime.datetime.now()
                await self.do_cycle()
                # wait till next cycle
                end = datetime.datetime.now()
                wait = 1 - (end - start).microseconds / float(1000000)
                if (wait > 0):
                    await asyncio.sleep(wait)
                else:
                    pass  # probably  we are overcomitted, but it's ok

                ops_total = ops_total + self.ops_sec
                cycle = cycle + 1

                if (cycle % 100) == 0:  # ~2 mins
                    logging.info("[AsyncTask %s] total ops: %s" % (
                        self.name, ops_total))
                    break
            logging.info("[AsyncTask %s] done!" % (self.name))
            t2 = time.perf_counter() - t
            logging.info(
                f'[AsyncTask {self.name}] {cycle} cycles took '
                f'{t2:0.2f} seconds.')
        except asyncio.CancelledError:
            logging.info("[AsyncTask %s] done!" % (self.name))
        except asyncio.InvalidStateError:
            logging.info(
                "[AsyncTask %s] caught invalid state!" % (self.name))

    async def do_cycle(self):
        for i in range(len(self.cbs)):
            self.cb = self.cbs[i]
            self.template = self.templates[i]
            sizes = self.template.get('size') or self.default_tsizes
            t_size = sizes[random.randint(0, len(sizes) - 1)]
            self.template['t_size'] = t_size
            if self.create_count > 0:
                count = self.create_count
                docs_to_expire = self.exp_count
                if docs_to_expire > 0:
                    await self.mset_batch(self.template, docs_to_expire,
                                          ttl=self.ttl,
                                          persist_to=self.persist_to,
                                          replicate_to=self.replicate_to,
                                          durability_level=self.durability_level)
                    count = count - docs_to_expire
                    count = int(count)
                await self.mset_batch(self.template, count,
                                      persist_to=self.persist_to,
                                      replicate_to=self.replicate_to,
                                      durability_level=self.durability_level)

            if self.update_count > 0:
                await self.mset_update(self.template, self.update_count, persist_to=self.persist_to,
                                 replicate_to=self.replicate_to,durability_level=self.durability_level)

            if self.get_count > 0:
                await self.mget_batch(self.get_count)

            if self.del_count > 0:
                await self.mdelete_batch(self.del_count,
                                         durability_level=self.durability_level)

    async def mset_batch(self, template, count, ttl=0, persist_to=0,
                         replicate_to=0,
                         durability_level=Durability.NONE):
        msg = {}
        keys = []
        cursor = 0
        j = 0

        template = resolveTemplate(template)
        for j in range(int(count)):
            self.i = self.i + 1
            msg[self.name + str(self.i)] = template
            keys.append(self.name + str(self.i))

            if ((j + 1) % self.batch_size) == 0:
                batch = keys[cursor:j + 1]
                await asyncio.gather(
                    *[self._mset(k, v) for k, v in msg.items()])
                self.memq.put_nowait(
                    {'start': batch[0], 'end': batch[-1]})
                msg = {}
                cursor = j
            elif j == (count - 1):
                batch = keys[cursor:]
                await asyncio.gather(
                    *[self._mset(k, v) for k, v in msg.items()])
                self.memq.put_nowait(
                    {'start': batch[0], 'end': batch[-1]})


    async def _mset(self, key, doc, ttl=0, persist_to=0, replicate_to=0,
                    durability_level=Durability.NONE):

        try:
            if persist_to != 0 or replicate_to != 0:
                durability = ClientDurability(
                    replicate_to=Cardinal(replicate_to),
                    persist_to=Cardinal(persist_to))
            else:
                durability = ServerDurability(durability_level)
            if ttl != 0:
                timedelta = datetime.timedelta(ttl)
                upsert_options = UpsertOptions(expiry=timedelta,
                                           durability=durability)
            else:
                upsert_options = UpsertOptions(durability=durability)
            await self.cb.upsert(key, doc, options=upsert_options)
        except TemporaryFailException:
            logging.warn(
                "temp failure during mset - cluster may be unstable")
        except TimeoutException:
            logging.warn(
                f"[{self.name}] cluster timed trying to handle mset")
        except NetworkException as nx:
            logging.error("network error")
            logging.error(nx)
        except Exception as ex:
            logging.error(ex)
            # self.isterminal = True

    async def mset_update(self, template, count, persist_to=0,
                          replicate_to=0,
                          durability_level=Durability.NONE):

        msg = {}
        batches = self.getKeys(count)
        template = resolveTemplate(template)
        if len(batches) > 0:

            for batch in batches:
                try:
                    for key in batch:
                        msg[key] = template
                    await asyncio.gather(
                        *[self._mset(k, v) for k, v in
                          msg.items()])
                except DocumentNotFoundException as nf:
                    logging.error(
                        "[{self.name}] update key not found!  %s: " % nf.key)
                except TimeoutException:
                    logging.warn(
                        "cluster timed out trying to handle mset - cluster may be unstable")
                except NetworkException as nx:
                    logging.error("network error")
                    logging.error(nx)
                except TemporaryFailException:
                    logging.warn(
                        "temp failure during mset - cluster may be unstable")
                except Exception as ex:
                    logging.error(ex)
                    # self.isterminal = True

    async def mget_batch(self, count):

        batches = self.getKeys(count)

        if len(batches) > 0:

            for batch in batches:
                await asyncio.gather(*[self.mget(k) for k in batch])

    async def mget(self, key):
        try:
            await self.cb.get(key)
        except DocumentNotFoundException as nf:
            logging.warn(
                f"[{self.name}] get key not found!  %s: " % nf.key)
            pass
        except TimeoutException:
            logging.warn(
                "cluster timed out trying to handle mget - cluster may be unstable")
        except NetworkException as nx:
            logging.error("network error")
            logging.error(nx)
        except Exception as ex:
            logging.error(ex)

    async def mdelete_batch(self, count,
                            durability_level=Durability.NONE):
        batches = self.getKeys(count, requeue=False)
        keys_deleted = 0

        # delete from buffer
        if len(batches) > 0:
            keys_deleted = await self._mdelete_batch(batches,
                                                     durability_level)
        else:
            pass

    async def _mdelete_batch(self, batches,
                             durability_level=Durability.NONE):
        keys_deleted = 0
        for batch in batches:
            if len(batch) > 0:
                keys_deleted = len(batch) + keys_deleted
            await asyncio.gather(*[self._mdelete(k) for k in batch])
        return keys_deleted

    async def _mdelete(self, key, durability_level=Durability.NONE):
        try:
            await self.cb.remove(key, RemoveOptions(
                durability=ServerDurability(durability_level)))
        except DocumentNotFoundException as nf:
            logging.warn(
                f"[{self.name}] get key not found!  %s: " % nf.key)
        except TimeoutException:
            logging.warn(
                "cluster timed out trying to handle mdelete - cluster may be unstable")
        except NetworkException as nx:
            logging.error("network error")
            logging.error(nx)
        except Exception as ex:
            logging.error(ex)
            # self.isterminal = True

    def getKeys(self, count, requeue=True):

        keys_retrieved = 0
        batches = []

        while keys_retrieved < count:

            # get keys
            keys = self.getKeysFromQueue(requeue)

            if len(keys) == 0:
                break

            # in case we got too many keys slice the batch
            need = count - keys_retrieved
            if (len(keys) > need):
                keys = keys[:need]

            keys_retrieved = keys_retrieved + len(keys)

            # add to batch
            batches.append(keys)

        return batches

    def getKeysFromQueue(self, requeue=True):

        # get key mapping and convert to keys
        keys = []
        key_map = self.getKeyMapFromLocalQueue(requeue)

        if key_map:
            keys = self.keyMapToKeys(key_map)

        return keys

    def keyMapToKeys(self, key_map):

        keys = []
        # reconstruct key-space
        prefix, start_idx = key_map['start'].split('_')
        prefix, end_idx = key_map['end'].split('_')

        for i in range(int(start_idx), int(end_idx) + 1):
            keys.append(prefix + "_" + str(i))

        return keys

    def fillq(self):

        if (self.consume_queue == None) and (self.ccq == None):
            return

        # put about 20 items into the queue
        for i in range(20):
            key_map = self.getKeyMapFromRemoteQueue()
            if key_map:
                self.memq.put_nowait(key_map)

        logging.info(
            "[Thread %s] filled %s items from  %s" % (
            self.name, self.memq.qsize(),
            self.consume_queue or self.ccq))

    def getKeyMapFromLocalQueue(self, requeue=True):

        key_map = None

        try:
            key_map = self.memq.get_nowait()
            if requeue:
                self.memq.put_nowait(key_map)
        except asyncio.QueueEmpty:
            # no more items
            self.fillq()

        return key_map

    def getKeyMapFromRemoteQueue(self, requeue=True):
        return None


class SDKClient(threading.Thread):

    def __init__(self, name, task, e):
        threading.Thread.__init__(self)
        self.name = name
        self.i = 0
        self.op_factor = CLIENTSPERPROCESS * PROCSPERTASK
        self.ops_sec = task['ops_sec']
        self.bucket = task['bucket']
        self.password = task['password']
        self.user_password = task['user_password']
        self.template = task['template']
        self.default_tsizes = task['sizes']
        self.create_count = int(task['create_count'] / self.op_factor)
        self.update_count = int(task['update_count'] / self.op_factor)
        self.get_count = int(task['get_count'] / self.op_factor)
        self.del_count = int(task['del_count'] / self.op_factor)
        self.exp_count = int(task['exp_count'] / self.op_factor)
        self.ttl = task['ttl']
        self.persist_to = task['persist_to']
        self.replicate_to = task['replicate_to']
        self.durability= task['durability']
        self.miss_perc = task['miss_perc']
        self.active_hosts = task['active_hosts']
        self.batch_size = 100
        self.memq = queue.Queue()
        self.consume_queue = task['consume_queue']
        self.standalone = task['standalone']
        self.ccq = None
        self.hotkey_batches = []

        if self.durability== None:
            self.durability_level=Durability.NONE
        elif self.durability== 'majority':
            self.durability_level=Durability.MAJORITY
        elif self.durability == 'majority_and_persist_on_master':
            self.durability_level=Durability.MAJORITY_AND_PERSIST_ON_MASTER
        elif self.durability == 'persist_to_majority':
            self.durability_level=Durability.PERSIST_TO_MAJORITY

        if self.ttl:
            self.ttl = int(self.ttl)

        if self.batch_size > self.create_count:
            self.batch_size = self.create_count

        self.active_hosts = task['active_hosts']

        addr = task['active_hosts'][random.randint(0, len(self.active_hosts) - 1)].split(':')
        host = addr[0]
        port = 8091
        if len(addr) > 1:
            port = addr[1]

        self.e = e
        self.cb = None
        self.cbs = []
        self.templates = []
        self.isterminal = False
        self.done = False

        try:
            # direct port for cluster_run
            port_mod = int(port) % 9000
            if port_mod != 8091:
                port = str(12000 + port_mod)
            auther = PasswordAuthenticator(self.bucket, self.user_password)
            endpoint = 'couchbase://{0}:{1}'.format(host,port)
            cluster = Cluster(endpoint, ClusterOptions(auther))
            collections = task['collections']
            for scope, _collections in collections.items():
                for collection in _collections:
                    template = copy.deepcopy(self.template)
                    template['kv']['scope'] = scope
                    template['kv']["collection"] = collection
                    self.templates.append(template)
                    try:
                        if collection == "default":
                            cb = cluster.bucket(self.bucket).default_collection()
                        else:
                            cb = cluster.bucket(self.bucket).scope(
                                scope).collection(collection)
                        cb.timeout = 30
                        self.cbs.append(cb)
                    except Exception as ex:
                        logging.error("[Thread %s] cannot reach %s "
                                      "for %s-%s" % (
                        self.name, endpoint, scope, collection))
                        logging.error(ex)
        except Exception as ex:

            logging.error("[Thread %s] cannot reach %s" % (self.name, endpoint))
            logging.error(ex)
            #self.isterminal = True

        logging.info("[Thread %s] started for workload: %s" % (self.name, task['id']))

    def run(self):

        cycle = ops_total = 0
        self.e.set()
        tracemalloc.start()
        while self.e.is_set() == True:

            start = datetime.datetime.now()

            # do an op cycle
            self.do_cycle()

            if self.isterminal == True:
                # some error occured during workload
                self.flushq(True)
                exit(-1)

            # wait till next cycle
            end = datetime.datetime.now()
            wait = 1 - (end - start).microseconds / float(1000000)
            if (wait > 0):
                time.sleep(wait)
            else:
                pass  # probably  we are overcomitted, but it's ok

            ops_total = ops_total + self.ops_sec
            cycle = cycle + 1

            if (cycle % 120) == 0:  # 2 mins
                logging.info("[Thread %s] total ops: %s" % (self.name, ops_total))
                self.flushq()

        self.flushq()
        logging.info("[Thread %s] done!" % (self.name))

    def flushq(self, flush_hotkeys=False):
        return  # todo for dirty keys

    def do_cycle(self):
        for i in range(self.cbs.__len__()):
            self.cb = self.cbs[i]
            self.template = self.templates[i]
            sizes = self.template.get('size') or self.default_tsizes
            t_size = sizes[random.randint(0, len(sizes) - 1)]
            self.template['t_size'] = t_size
            if self.create_count > 0:

                count = self.create_count
                docs_to_expire = self.exp_count
                # check if we need to expire some docs
                if docs_to_expire > 0:
                    # create an expire batch
                    self.mset(self.template, docs_to_expire, ttl=self.ttl, persist_to=self.persist_to,
                              replicate_to=self.replicate_to,durability_level=self.durability_level)
                    count = count - docs_to_expire
                    count = int(count)
                self.mset(self.template, count, persist_to=self.persist_to, replicate_to=self.replicate_to,durability_level=self.durability_level)

            if self.update_count > 0:
                self.mset_update(self.template, self.update_count, persist_to=self.persist_to,
                                 replicate_to=self.replicate_to,durability_level=self.durability_level)

            if self.get_count > 0:
                self.mget(self.get_count)

            if self.del_count > 0:
                self.mdelete(self.del_count,durability_level=self.durability_level)
        snapshot = tracemalloc.take_snapshot()
        self.display_top(snapshot)

    def mset(self, template, count, ttl=0, persist_to=0, replicate_to=0,durability_level=Durability.NONE):
        msg = {}
        keys = []
        cursor = 0
        j = 0

        template = resolveTemplate(template)
        for j in range(int(count)):
            self.i = self.i + 1
            msg[self.name + str(self.i)] = template
            keys.append(self.name + str(self.i))

            if ((j + 1) % self.batch_size) == 0:
                batch = keys[cursor:j + 1]
                self._mset(msg, ttl, persist_to=persist_to, replicate_to=replicate_to,durability_level=durability_level)
                self.memq.put_nowait({'start': batch[0], 'end': batch[-1]})
                msg = {}
                cursor = j
            elif j == (count - 1):
                batch = keys[cursor:]
                self._mset(msg, ttl, persist_to=persist_to, replicate_to=replicate_to)
                self.memq.put_nowait({'start': batch[0], 'end': batch[-1]})

    def _mset(self, msg, ttl=0, persist_to=0, replicate_to=0,durability_level=Durability.NONE):

        try:
            self.cb.upsert_multi(msg, ttl=ttl, persist_to=persist_to, replicate_to=replicate_to,durability_level=durability_level)
        except TemporaryFailException:
            logging.warn("temp failure during mset - cluster may be unstable")
        except TimeoutException:
            logging.warn("cluster timed trying to handle mset")
        except NetworkException as nx:
            logging.error("network error")
            logging.error(nx)
        except Exception as ex:
            logging.error(ex)
            #self.isterminal = True

    def mset_update(self, template, count, persist_to=0, replicate_to=0,durability_level=Durability.NONE):

        msg = {}
        batches = self.getKeys(count)
        template = resolveTemplate(template)
        if len(batches) > 0:

            for batch in batches:
                try:
                    for key in batch:
                        msg[key] = template
                    self.cb.upsert_multi(msg, persist_to=persist_to, replicate_to=replicate_to,durability_level=durability_level)
                except DocumentNotFoundException as nf:
                    logging.error("update key not found!  %s: " % nf.key)
                except TimeoutException:
                    logging.warn("cluster timed out trying to handle mset - cluster may be unstable")
                except NetworkException as nx:
                    logging.error("network error")
                    logging.error(nx)
                except TemporaryFailException:
                    logging.warn("temp failure during mset - cluster may be unstable")
                except Exception as ex:
                    logging.error(ex)
                    #self.isterminal = True

    def mget(self, count):

        batches = []
        if self.miss_perc > 0:
            batches = self.getCacheMissKeys(count)
        else:
            batches = self.getKeys(count)

        if len(batches) > 0:

            for batch in batches:
                try:
                    self.cb.get_multi(batch)
                except DocumentNotFoundException as nf:
                    logging.warn("get key not found!  %s: " % nf.key)
                    pass
                except TimeoutException:
                    logging.warn("cluster timed out trying to handle mget - cluster may be unstable")
                except NetworkException as nx:
                    logging.error("network error")
                    logging.error(nx)
                except Exception as ex:
                    logging.error(ex)
                    #self.isterminal = True

    def mdelete(self, count,durability_level=Durability.NONE):
        batches = self.getKeys(count, requeue=False)
        keys_deleted = 0

        # delete from buffer
        if len(batches) > 0:
            keys_deleted = self._mdelete(batches,durability_level)
        else:
            pass

    def _mdelete(self, batches,durability_level=Durability.NONE):
        keys_deleted = 0
        for batch in batches:
            try:
                if len(batch) > 0:
                    keys_deleted = len(batch) + keys_deleted
                    self.cb.remove_multi(batch,durability_level=durability_level)
            except DocumentNotFoundException as nf:
                logging.warn("get key not found!  %s: " % nf.key)
            except TimeoutException:
                logging.warn("cluster timed out trying to handle mdelete - cluster may be unstable")
            except NetworkException as nx:
                logging.error("network error")
                logging.error(nx)
            except Exception as ex:
                logging.error(ex)
                #self.isterminal = True

        return keys_deleted

    def getCacheMissKeys(self, count):

        # returns batches of keys where first batch contains # of keys to miss
        keys_retrieved = 0
        batches = []
        miss_keys = []

        num_to_miss = int(((self.miss_perc / float(100)) * count))
        miss_batches = self.getKeys(num_to_miss, force_stale=True)

        if len(self.hotkey_batches) == 0:
            # hotkeys are taken off queue and cannot be reused
            # until workload is flushed
            need = count - num_to_miss
            self.hotkey_batches = self.getKeys(need, requeue=False)

        batches = miss_batches + self.hotkey_batches
        return batches

    def getKeys(self, count, requeue=True, force_stale=False):

        keys_retrieved = 0
        batches = []

        while keys_retrieved < count:

            # get keys
            keys = self.getKeysFromQueue(requeue, force_stale=force_stale)

            if len(keys) == 0:
                break

            # in case we got too many keys slice the batch
            need = count - keys_retrieved
            if (len(keys) > need):
                keys = keys[:need]

            keys_retrieved = keys_retrieved + len(keys)

            # add to batch
            batches.append(keys)

        return batches

    def getKeysFromQueue(self, requeue=True, force_stale=False):

        # get key mapping and convert to keys
        keys = []
        key_map = None

        # priority to stale queue
        if force_stale:
            key_map = self.getKeyMapFromRemoteQueue(requeue)

        # fall back to local qeueue
        if key_map is None:
            key_map = self.getKeyMapFromLocalQueue(requeue)

        if key_map:
            keys = self.keyMapToKeys(key_map)

        return keys

    def keyMapToKeys(self, key_map):

        keys = []
        # reconstruct key-space
        prefix, start_idx = key_map['start'].split('_')
        prefix, end_idx = key_map['end'].split('_')

        for i in range(int(start_idx), int(end_idx) + 1):
            keys.append(prefix + "_" + str(i))

        return keys

    def fillq(self):

        if (self.consume_queue == None) and (self.ccq == None):
            return

        # put about 20 items into the queue
        for i in range(20):
            key_map = self.getKeyMapFromRemoteQueue()
            if key_map:
                self.memq.put_nowait(key_map)

        logging.info(
            "[Thread %s] filled %s items from  %s" % (self.name, self.memq.qsize(), self.consume_queue or self.ccq))

    def getKeyMapFromLocalQueue(self, requeue=True):

        key_map = None

        try:
            key_map = self.memq.get_nowait()
            if requeue:
                self.memq.put_nowait(key_map)
        except queue.Empty:
            # no more items
            self.fillq()

        return key_map

    def getKeyMapFromRemoteQueue(self, requeue=True):
        return None

    def display_top(self, snapshot, key_type='lineno', limit=10):
        snapshot = snapshot.filter_traces((
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            ))
        top_stats = snapshot.statistics(key_type)

        print("Top %s lines" % limit)
        for index, stat in enumerate(top_stats[:limit], 1):
            frame = stat.traceback[0]
            print("#%s: %s:%s: %.1f KiB"
                  % (index, frame.filename, frame.lineno,
                     stat.size / 1024))
            line = linecache.getline(frame.filename,
                                     frame.lineno).strip()
            if line:
                print('    %s' % line)

        other = top_stats[limit:]
        if other:
            size = sum(stat.size for stat in other)
            print("%s other: %.1f KiB" % (len(other), size / 1024))
        total = sum(stat.size for stat in top_stats)
        print("Total allocated size: %.1f KiB\n\n" % (total / 1024))


class SDKProcess(Process):

    def __init__(self, id, task):

        super(SDKProcess, self).__init__()

        self.task = task
        self.id = id
        self.clients = []

    async def shut_down(self, sig, loop):
        print(f'Caught {sig.name}\n')
        try:
            tasks = [t for t in asyncio.all_tasks() if
                     t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()

            results = await asyncio.gather(*tasks,
                                           return_exceptions=True)
            print(f'Cancelled tasks finished. Results:\n{results}')
        except asyncio.CancelledError as ex:
            print('Cancelled error: ' + str(ex))
        except asyncio.InvalidStateError as ex:
            print('InvalidStateError error: ' + str(ex))
        except Exception as ex:
            print('Exception: ' + str(ex))
        finally:
            await asyncio.sleep(0)

        print('\nStopping loop...')
        loop.stop()

    async def create_clients(self):
        tasks_per_process = self.task['tasks_per_process']
        for i in range(tasks_per_process):
            task_name = str(_random_string(4)) + "-" + str(
                os.getpid()) + str(i) + "_"
            self.clients.append(
                await SDKClientAsync.create(self.task, task_name,
                                            i))

    async def run_async(self):
        try:
            clients = self.clients

            tasks = list(map(
                lambda c: asyncio.get_event_loop().create_task(c.run(),
                                                               name=c.name),
                clients))

            while len(clients) > 0:
                done, pending = await asyncio.wait(tasks,
                                                   return_when=asyncio.FIRST_EXCEPTION)
                if len(done) == len(clients):
                    break
                for i, r in enumerate(done):
                    if isinstance(r.exception(), Exception):
                        dead_client_idx = -1
                        for idx, c in enumerate(clients):
                            if c.name == r.get_name():
                                dead_client_idx = idx
                        if dead_client_idx >= 0:
                            del clients[dead_client_idx]
                            task_name = str(
                                _random_string(4)) + "-" + str(
                                os.getpid()) + str(
                                dead_client_idx) + "_"
                            new_client = await SDKClientAsync.create(
                                self.task,
                                task_name, dead_client_idx)
                            clients.append(new_client)
                            tasks = list(pending)
                            tasks.append(
                                asyncio.get_event_loop().create_task(
                                    new_client.run(),
                                    name=new_client.name))
        except asyncio.CancelledError as ex:
            print('run_async() task(s) cancelled - shutting down.')

    def run(self):

        logging.info("[Process %s] started workload: %s" % (self.id, self.task['id']))
        asyncio.set_event_loop(get_event_loop())
        loop = asyncio.get_event_loop()
        try:
            loop.add_signal_handler(signal.SIGINT,
                                    functools.partial(
                                        asyncio.ensure_future,
                                        self.shut_down(
                                            signal.SIGINT,
                                            loop)))
            loop.run_until_complete(self.create_clients())
            while True:
                if len(self.clients) == 0:
                    loop.run_until_complete(self.create_clients())
                loop.run_until_complete(self.run_async())
        except KeyboardInterrupt:
            pass
        except Exception as ex:
            import traceback
            traceback.print_exc()
        finally:
            pass

    def terminate(self):

        super(SDKProcess, self).terminate()
        logging.info("[Process %s] terminated workload: %s" % (self.id, self.task['id']))


def _random_string(length):
    length = int(length)
    return (("%%0%dX" % (length * 2)) % random.getrandbits(length * 8))


def _random_int(length):
    return random.randint(10 ** (length - 1), (10 ** length) - 1)


def _random_float(length):
    return _random_int(length) / (10.0 ** (length / 2))


def kill_nprocs(id_, kill_num=None):
    if id_ in PROCSSES:
        procs = PROCSSES[id_]
        del PROCSSES[id_]

        if kill_num == None:
            kill_num = len(procs)

        for i in range(kill_num):
            procs[i].terminate()

def kill_all_proc():
    for procs in PROCSSES.values():
        for proc in procs:
            proc.terminate()

def start_client_processes(task, standalone=False):
    task['standalone'] = standalone
    max_process = task['max_process']
    workload_id = task['id']
    PROCSSES[workload_id] = []
    for i in range(max_process):
        # set process id and provide queue
        p_id = (i) * CLIENTSPERPROCESS
        p = SDKProcess(p_id, task)

        # start
        p.start()

        # archive
        PROCSSES[workload_id].append(p)

def init(message):
    body = message.body
    task = None

    if str(body) == 'init':
        return

    try:
        task = json.loads(str(body))

    except Exception:
        print("Unable to parse workload task")
        print(body)
        return

    if task['active'] == False:

        # stop processes running a workload
        workload_id = task['id']
        kill_nprocs(workload_id)


    else:
        try:
            start_client_processes(task)

        except Exception as ex:
            print("Unable to start workload processes")
            print(ex)


def resolveTemplate(template):
    conversionFuncMap = {'str': lambda n: _random_string(n), 'int': lambda n: _random_int(n),
        'flo': lambda n: _random_float(n), 'boo': lambda n: (True, False)[random.randint(0, 1)], }

    def convToType(val):
        mObj = re.search(r"(.*?)(\$)([A-Za-z]+)(\d+)?(.*)", val)
        if mObj:
            prefix, magic, type_, len_, suffix = mObj.groups()
            len_ = len_ or 5
            if type_ in conversionFuncMap.keys():
                val = conversionFuncMap[type_](int(len_))
                val = "{}{}{}".format(prefix, val, suffix)
                if len(prefix) == 0 and len(suffix) == 0:
                    # use raw types
                    if type_ == "int":
                        val = int(val)
                    if type_ == "boo":
                        val = bool(val)
                    if type_ == "flo":
                        val = float(val)

        if type(val) == str and '$' in val:
            # convert remaining strings
            return convToType(val)

        return val

    def resolveList(li):
        rc = []
        for item in li:
            val = item
            if type(item) == list:
                val = resolveList(item)
            elif item and type(item) == str and '$' in item:
                val = convToType(item)
            rc.append(val)

        return rc

    def resolveDict(di):
        rc = {}
        for k, v in di.items():
            val = v
            if type(v) == dict:
                val = resolveDict(v)
            elif type(v) == list:
                val = resolveList(v)
            elif v and type(v) == str and '$' in v:
                val = convToType(v)
            rc[k] = val
        return rc

    t_size = template['t_size']
    kv_template = resolveDict(template['kv'])
    kv_size = sys.getsizeof(kv_template) / 8
    if kv_size < t_size:
        padding = _random_string(t_size - kv_size)
        kv_template.update({"padding": padding})

    return kv_template
