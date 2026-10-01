"""Fixed Quota consumer reusing authenticated at-most-once Guard transport."""
from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer


class QuotaPolicyConsumer(GuardPolicyConsumer):
    _signature = "public.aip_quota_activation_a0v_130(text,text,text,text,text,text,text,text,boolean)"
    _function = "public.aip_quota_activation_a0v_130"
