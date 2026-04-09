"""Quick verification that episode IDs differ across resets."""
import sys
sys.path.insert(0, 'd:/OpenENV/tool_chain_env')
from server.tool_chain_env_environment import ToolChainEnvironment

print("=== Task1: 3 resets (user IDs must differ) ===")
env1 = ToolChainEnvironment('task1')
ids1 = []
for i in range(3):
    obs = env1.reset()
    uid = env1._episode_data['target_user_id']
    ids1.append(uid)
    in_desc = str(uid) in obs.task_description
    print("  Reset %d: user_id=%s  in_desc=%s" % (i+1, uid, in_desc))
print("  All unique across resets: %s" % (len(set(ids1)) == 3))

print()
print("=== Task2: 3 resets (order IDs must be ORD-XXNNNN and differ) ===")
env2 = ToolChainEnvironment('task2')
ids2 = []
for i in range(3):
    obs = env2.reset()
    oid = env2._episode_data['target_order_id']
    ids2.append(oid)
    in_desc = oid in obs.task_description
    fmt_ok = oid.startswith("ORD-") and len(oid) == 10
    print("  Reset %d: order_id=%s  in_desc=%s  format_ok=%s" % (i+1, oid, in_desc, fmt_ok))
print("  All unique across resets: %s" % (len(set(ids2)) == 3))
print()
print("DONE - ID randomisation verified.")
