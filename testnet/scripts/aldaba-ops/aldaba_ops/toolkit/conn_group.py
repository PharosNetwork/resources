from invoke import Context
from patchwork.files import exists
from fabric.group import Group, GroupResult, GroupException, Queue, ExceptionHandlingThread
from fabric.connection import Connection
from fabric.util import debug
from functools import wraps
from aldaba_ops.toolkit import logs

import os
import shutil

def is_local(host: str):
    return host in ['127.0.0.1', 'localhost']

def sync(conn :Context, source :str, target :str, rsync_opts :str='-avzL'):
    cmd = f'rsync {rsync_opts} {source} {conn.user}@{conn.host}:{target}'
    logs.debug(cmd)
    return conn.local(cmd)

def sync_back(conn :Context, source :str, target :str, rsync_opts :str='-avzL'):
    cmd = f'rsync {rsync_opts} {conn.user}@{conn.host}:{source} {target}'
    logs.debug(cmd)
    return conn.local(cmd)

def run_decorator(fn):
    @wraps(fn)
    def wrapped(conn, command, **kwargs):
        logs.debug(command)
        return fn(conn, command, **kwargs)
    return wrapped

# add sync method to fabric Connection
setattr(Connection, 'sync', sync)
setattr(Connection, 'sync_back', sync_back)
# decrate run method of fabric Connection
Connection.run = run_decorator(Connection.run)

class LocalConnection(Context):
    def __enter__(self):
        return self

    def __exit__(self):
        pass

    def run(self, command, **kwargs):
        logs.debug(command)
        return super().run(command, **kwargs)

    def sync(self, source, target, rsync_opts='-av'):
        return self.run(f'rsync {rsync_opts} {source} 127.0.0.1:{target}')

    def clean_folder(self, folder: str, except_: str=None):
        if not os.path.exists(folder):
            return
        logs.debug(f'clean folder {folder}, except: {except_}')
        for file in os.scandir(folder):
            if not except_ or not file.path.endswith(except_):
                try:
                    shutil.rmtree(file.path)
                except OSError:
                    os.remove(file.path)


def thread_worker(cxn, queue, method, args, kwargs):
    # support run function in ConcurrentGroup
    if callable(method):
        result = method(cxn, *args, **kwargs)
    else:
        result = getattr(cxn, method)(*args, **kwargs)
    queue.put((cxn, result))


class ConcurrentGroup(Group):
    """
    Subclass of `fabric.group.Group` which call multiple connection concurrently.
    """
    def _do(self, method, *args, **kwargs):
        results = GroupResult()
        queue = Queue()
        threads = []
        for cxn in self:
            thread = ExceptionHandlingThread(
                target=thread_worker,
                kwargs=dict(
                    cxn=cxn,
                    queue=queue,
                    method=method,
                    args=args,
                    kwargs=kwargs,
                ),
            )
            threads.append(thread)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        while not queue.empty():
            cxn, result = queue.get(block=False)
            results[cxn] = result
        excepted = False
        for thread in threads:
            wrapper = thread.exception()
            if wrapper is not None:
                cxn = wrapper.kwargs["kwargs"]["cxn"]
                results[cxn] = wrapper.value
                excepted = True
        if excepted:
            raise GroupException(results)
        return results

    def call(self, func, *args, **kwargs):
        self._do(func, *args, **kwargs)

    def sync(self, source, target, rsync_opts='-av'):
        self._do("sync", source, target, rsync_opts=rsync_opts)

local = LocalConnection()
