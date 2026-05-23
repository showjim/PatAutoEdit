"""Manual multiprocess smoke test for dispatch_config_parallel."""
import os
from multiprocessing import Pool, Manager
from src.logger import Logger
from src.main import dispatch_config_parallel
from src.atp_handler import analyse_merge_config, build_config_from_classical


def run():
    sample_dir = 'Sample'
    atp_files = sorted([os.path.join(sample_dir, f) for f in os.listdir(sample_dir) if f.lower().endswith('.atp')])
    logger = Logger()

    queue = Manager().Queue()
    counter = Manager().Value('i', 0)

    def _cb(_):
        counter.value += 1

    # Classical path
    cfg = build_config_from_classical(os.path.join(sample_dir, 'Sample_ATP.csv'),
                                      'DSSC Capture', 'TDO', 'Single', 'Cycle')
    mp_logger = Logger(gui_callback=queue.put)
    with Pool(processes=4) as pool:
        total = dispatch_config_parallel(pool, atp_files, cfg, mp_logger, '', _cb)
        pool.close(); pool.join()
    print(f'Classical parallel: submitted={total} completed={counter.value}')

    # Simple path
    counter.value = 0
    cfg2 = analyse_merge_config(os.path.join(sample_dir, 'Sample_ATP - simple.csv'), logger)
    with Pool(processes=4) as pool:
        total2 = dispatch_config_parallel(pool, atp_files, cfg2, mp_logger, '', _cb)
        pool.close(); pool.join()
    print(f'Simple parallel: submitted={total2} completed={counter.value}')

    # Drain a few log messages
    drained = 0
    while not queue.empty() and drained < 5:
        print('[mp-log]', queue.get())
        drained += 1


if __name__ == '__main__':
    run()
