
"""
This is meant to be executed using mpirun.

"""

if __name__ == '__main__':
    import sys
    import os
    import traceback
    import json

    from multiprocessing.managers import SyncManager
    from multiprocessing import Process, Queue

    from mpi4py import MPI
    from testflo.util import _get_parser, get_memory_usage
    from testflo.runner import TestRunner, exit_codes
    from testflo.test import Test
    from testflo.cover import save_coverage
    from testflo.options import get_options


    exitcode = 0  # use 0 for exit code of all ranks != 0 because otherwise,
                  # MPI will terminate other processes

    # connect to the shared queue and dict
    class QueueManager(SyncManager): pass

    QueueManager.register('get_queue')
    QueueManager.register('run_test')
    QueueManager.register('dict_handler')
    manager = QueueManager(address=('', get_options().port), authkey=b'foo')
    manager.connect()
    d = manager.dict_handler()  # test objects keyed by test spec
    q = None

    try:
        try:
            comm = MPI.COMM_WORLD
            test = d.get_item(sys.argv[-1])
            test.run()
        except:
            print(traceback.format_exc())
            test.status = 'FAIL'
            test.err_msg = traceback.format_exc()

        # collect results
        results = comm.gather(test, root=0)
        if comm.rank == 0:
            q = manager.get_queue()

            total_mem_usage = sum(r.memory_usage for r in results)
            test.memory_usage = total_mem_usage

            # check for errors and record error message
            for r in results:
                if r.status != 'OK':
                    test.err_msg = r.err_msg
                    test.status = 'FAIL'
                    exitcode = exit_codes[r.status]
                    break

        save_coverage()

    except Exception:
        test.err_msg = traceback.format_exc()
        test.status = 'FAIL'
        exitcode = exit_codes['FAIL']

    finally:
        sys.stdout.flush()
        sys.stderr.flush()

        if comm.rank == 0 and q is not None:
            q.put(test)

        sys.exit(exitcode)
