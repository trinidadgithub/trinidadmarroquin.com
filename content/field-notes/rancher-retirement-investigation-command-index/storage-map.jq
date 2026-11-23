# Local snapshot analysis only. Supply each kubectl List via --slurpfile.
def checked($input; $label):
  if ($input | length) != 1 then error($label + ": expected exactly one JSON document")
  elif ($input[0].items | type) != "array" then error($label + ": expected a Kubernetes List")
  elif any($input[0].items[];
      type != "object" or (.metadata.name | type) != "string" or .metadata.name == "")
    then error($label + ": item has no valid metadata.name")
  else $input[0].items end;

checked($pods; "pods") as $P |
checked($pvcs; "pvcs") as $C |
checked($pvs; "pvs") as $V |
checked($attachments; "attachments") as $A |
if any(($P + $C)[]; (.metadata.namespace | type) != "string")
then error("pods and pvcs require explicit namespaces") else . end |
[$P[] as $pod | $pod.spec.volumes[]? |
 select(.persistentVolumeClaim != null) |
 {namespace: $pod.metadata.namespace, pod: $pod.metadata.name,
  pod_uid: $pod.metadata.uid, phase: $pod.status.phase,
  deleting: $pod.metadata.deletionTimestamp, node: $pod.spec.nodeName,
  claim: .persistentVolumeClaim.claimName}] as $R |
{
  counts: {pods: ($P|length), pvcs: ($C|length), pvs: ($V|length),
           attachments: ($A|length)},
  volumes: [$V[] as $pv |
    {pv: $pv.metadata.name, pv_uid: $pv.metadata.uid,
     reclaim_policy: $pv.spec.persistentVolumeReclaimPolicy,
     claim_ref: $pv.spec.claimRef,
     csi_driver: $pv.spec.csi.driver, volume_handle: $pv.spec.csi.volumeHandle,
     claims: [$C[] | select(.spec.volumeName == $pv.metadata.name) | . as $claim |
       {namespace: .metadata.namespace, name: .metadata.name, uid: .metadata.uid,
        phase: .status.phase, deleting: .metadata.deletionTimestamp,
        finalizers: (.metadata.finalizers // []),
        consumers: [$R[] | select(.namespace == $claim.metadata.namespace
                              and .claim == $claim.metadata.name)]}],
     attachments: [$A[] | select(.spec.source.persistentVolumeName == $pv.metadata.name) |
       {name: .metadata.name, node: .spec.nodeName, attacher: .spec.attacher,
        attached: .status.attached, deleting: .metadata.deletionTimestamp,
        detach_error: .status.detachError.message}]}],
  claims_without_listed_pv: [$C[] |
    select(.spec.volumeName as $name | all($V[]; .metadata.name != $name)) |
    {namespace: .metadata.namespace, claim: .metadata.name, pv: .spec.volumeName}],
  pod_claims_without_listed_pvc: [$R[] as $ref |
    select(all($C[]; .metadata.namespace != $ref.namespace or .metadata.name != $ref.claim)) |
    $ref],
  attachments_without_listed_pv: [$A[] |
    select(.spec.source.persistentVolumeName as $name | all($V[]; .metadata.name != $name)) |
    {name: .metadata.name, pv: .spec.source.persistentVolumeName,
     node: .spec.nodeName, attached: .status.attached}]
}
