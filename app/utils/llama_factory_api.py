import sys

# sys.path.append(r"I:\\suzhou\\大模型\\LargeModel_backend\LLaMA-Factory")

import os

# import src.llmtuner.webui.runner as runner
# import src.train_bash as train_bash
# from src.api.index import TuneManager


# def test():
#     print('################')
#     print(os.environ.get('PYTHONPATH'))
#     instance = runner.Runner(manager=None)
#     # train_bash.run_exp()

def status_callback(info):
    print(f'status_callback:{info}')


def start_train(large_model_id):
    pass
    # TuneManager.start_train(status_callback, large_model_id)
