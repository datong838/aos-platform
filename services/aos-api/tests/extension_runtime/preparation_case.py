"""Real preparation commit followed by ACK loss must retain the same owner."""
import asyncio
from aos_api.extension_runtime.preparation_consumer import PreparationConsumer


async def prepare_with_ack_recovery(host,connect,operation):
    original_ack=host.outbox.ack
    lost=[]
    def failed(conn,**kwargs):
        original_ack(conn,**kwargs)
        lost.append(kwargs['lease'])
        raise RuntimeError('named preparation ACK rollback')
    host.outbox.ack=failed
    try:await host.run_once()
    except RuntimeError as exc:assert str(exc)=='named preparation ACK rollback'
    else:raise AssertionError('expected preparation ACK rollback')
    job=host.job
    assert job is not None and len(lost)==1
    assert str(job.plan.operation_id)==str(operation)
    def resource_state():
        with connect() as conn:
            return conn.execute('SELECT resource_id,container_id,observed_release FROM extension_runtime_resource_lease ORDER BY resource_id').fetchall()
    before=await asyncio.to_thread(resource_state)
    assert len(before)==len(job.plan.members) and all(r['container_id'] and r['observed_release'] is False for r in before)
    def expire():
        with connect() as conn:
            assert conn.execute('SELECT delivered_at FROM extension_runtime_outbox WHERE event_id=%s',
                (lost[0].event_id,)).fetchone()=={'delivered_at':None}
            conn.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second',next_attempt=clock_timestamp()-interval '1 day' WHERE event_id=%s",(lost[0].event_id,))
    await asyncio.to_thread(expire)
    original_start=host.worker.start
    async def forbidden(**kwargs):raise AssertionError('prepared resource created twice')
    host.worker.start=forbidden
    host.outbox.ack=original_ack
    fresh=PreparationConsumer(connect=host.connect,worker=host.worker,installation_id=host.installation,**host.scope)
    try:
        result=await host.run_once()
        assert str(result.operation_id)==str(operation) and result.operation_status=='succeeded'
        assert host.job is job
        for _ in range(30):
            if await fresh.run_once() is None:break
        else:raise AssertionError('bounded preparation drain did not finish')
        assert fresh.job is None
        assert await asyncio.to_thread(resource_state)==before
        await job.check_health()
        return result
    finally:
        await fresh.stop()
        host.worker.start=original_start
