"""Actual signed owner delivery with isolated post-commit ACK loss."""
import asyncio
from aos_api.extension_runtime.owned_control_consumer import OwnedControlConsumer


async def deliver_with_ack_recovery(consumer,connect,operation_id):
    original=consumer.outbox.ack
    lost=[]
    def fail_ack(conn,**kwargs):
        original(conn,**kwargs)
        lost.append(kwargs['lease'])
        raise RuntimeError('named owned ACK rollback')
    consumer.outbox.ack=fail_ack
    try:
        await consumer.run_once()
    except RuntimeError as exc:
        assert str(exc)=='named owned ACK rollback'
    else:raise AssertionError('ACK failure was not observed')
    assert len(lost)==1 and str(lost[0].operation_id)==str(operation_id)
    def state():
        with connect() as conn:
            return (conn.execute('SELECT status,revision FROM extension_runtime_operation WHERE operation_id=%s',
                (operation_id,)).fetchone(),conn.execute('SELECT revision,execution_epoch FROM extension_runtime_binding').fetchall())
    before=await asyncio.to_thread(state)
    assert before[0]['status']=='succeeded'
    def expire():
        with connect() as conn:
            assert conn.execute('SELECT delivered_at FROM extension_runtime_outbox WHERE event_id=%s',
                (lost[0].event_id,)).fetchone()=={'delivered_at':None}
            conn.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second',next_attempt=clock_timestamp()-interval '1 day' WHERE event_id=%s",(lost[0].event_id,))
    await asyncio.to_thread(expire)
    fresh=OwnedControlConsumer(connect=consumer.connect,job=consumer.job,kind=consumer.kind,**consumer.scope)
    method='verify' if consumer.kind=='runtime-verify' else 'enable'
    original_command=getattr(consumer.job,method)
    async def forbidden(**kwargs):raise AssertionError('committed owner command replayed')
    setattr(consumer.job,method,forbidden)
    try:
        result=await fresh.run_once()
        assert str(result.operation_id)==str(operation_id) and result.operation_status=='succeeded'
        assert result.delivery_status=='acknowledged'
        for _ in range(30):
            if await fresh.run_once() is None:break
        else:raise AssertionError('bounded owned event drain did not finish')
        assert await asyncio.to_thread(state)==before
        return result
    finally:
        await fresh.wait_idle()
        setattr(consumer.job,method,original_command)
