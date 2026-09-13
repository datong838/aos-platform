"""Read-only withdrawal hints; command authority stays in the locked Owner."""
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest, require_pristine_withdrawal
from aos_api.extension_runtime.storage_ports import require_runtime_role


def withdrawal_hint(conn, *, scope, row, origin, receipt_ref):
    require_runtime_role(conn,org_id=scope.org_id,project_id=scope.project_id,protected_tables=(
        'public.extension_dispatch_cutover_operation','public.automation_schedule_binding',
        'public.ecommerce_growth_runtime_command_receipt','public.extension_operation_dispatch_binding'))
    installation=conn.execute('''SELECT etag_version FROM public.bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
        (*scope.key,origin['installationId'])).fetchone()
    if installation is None:raise LookupError('registration installation unavailable')
    request=RegistrationWithdrawalRequest(registrationReceiptRef=receipt_ref,
        expectedInstallationEtag=installation['etag_version'],idempotencyKey='status-preview')
    # Cutover history is already restricted to the control maintainer. No write
    # entry is invoked and no new privileges are granted to either role.
    conn.execute('SET LOCAL ROLE aos_extension_maintainer')
    cutovers=conn.execute('''SELECT count(*) AS n FROM public.extension_dispatch_cutover_operation
        WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s''',
        (*scope.key,origin['groupId'])).fetchone()['n']
    conn.execute('SET LOCAL ROLE aos_runtime')
    operations=[item['operationId'] for item in origin['dispatchSnapshot']]
    dependencies=conn.execute('''SELECT
        (SELECT count(*) FROM public.automation_schedule_binding
          WHERE org_id=%s AND project_id=%s AND operation_id=ANY(%s)) +
        (SELECT count(*) FROM public.ecommerce_growth_runtime_command_receipt
          WHERE org_id=%s AND project_id=%s AND operation_id=ANY(%s)) AS n''',
        (*scope.key,operations,*scope.key,operations)).fetchone()['n']
    result=dict(expectedInstallationEtag=request.expectedInstallationEtag,
        allowedActions=[],withdrawalReason='dependent_history')
    if cutovers or dependencies:return result
    rows=conn.execute('''SELECT jsonb_build_object(
        'operationId',operation_id,'handlerKind',handler_kind,'installationId',installation_id,
        'generation',generation,'executionEpoch',execution_epoch,'operationFence',operation_fence,
        'revision',revision,'cutoverGroupId',cutover_group_id::text,'cutoverGroupRevision',cutover_group_revision) AS item
        FROM public.extension_operation_dispatch_binding
        WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s ORDER BY operation_id''',
        (*scope.key,origin['groupId'])).fetchall()
    try:
        require_pristine_withdrawal(row=row,scope=scope,request=request,
            dispatch_snapshot=[item['item'] for item in rows],cutover_count=cutovers,dependency_count=dependencies)
    except ValueError:
        # The caller strictly decoded the immutable origin before this read.
        # A mismatched current snapshot is a display blocker, never authority.
        result['withdrawalReason']='dispatch_changed'
    else:
        result.update(allowedActions=['withdraw'],withdrawalReason='unused_origin')
    return result
