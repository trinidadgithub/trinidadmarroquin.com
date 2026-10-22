+++
title = 'The Node Was Ready. The Volume Wasn’t.'
date = 2026-10-22T00:00:00-05:00
draft = false
description = 'A field note on an RKE2 worker recovery where HPE CSI reported attachment but an offline iSCSI volume never appeared in the guest.'
tags = ['kubernetes', 'rke2', 'csi', 'iscsi', 'storage', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

The worker came back `Ready`. Its CSI driver registered. Kubernetes reported that the volume attached. Alertmanager still could not start on that worker because the expected disk never appeared in the guest.

This happened during planned maintenance of Rancher-managed RKE2 worker VMs. The VMs were being powered down to enable `disk.EnableUUID = TRUE`, first in UAT and then in production. The NotReady-to-Ready transitions were part of that work, not a mysterious cluster outage. The production failure involved an HPE Nimble `ReadWriteOnce` volume presented over iSCSI. It needed to move with an Alertmanager pod from one worker to another.

The interesting boundary was not whether Kubernetes *said* the volume was attached. It was whether the storage backend had left that volume online long enough for the new worker to discover its LUN.

## The Event That Changed the Question

The replacement pod landed on a second worker at approximately 19:47 UTC. A brief `Multi-Attach` warning appeared while the previous placement was being released. By 19:47:16, Kubernetes recorded `SuccessfulAttachVolume`. That warning was transient; a persistent old-node attachment lock did not explain what followed.

At 19:47:48 the first `FailedMount` event said the CSI node plugin could not find the device with the volume's expected serial. The event was aggregated 19 times through 20:19:42. Those timestamps span 31 minutes and 54 seconds of observed failures. They do **not** establish that the application was down continuously for precisely that interval, nor do they enumerate every staging attempt.

The node driver had received publish metadata for iSCSI LUN 0 and repeatedly scanned for it. In the version of the HPE driver in use, the serial-not-found error comes from [device matching after the scan and login attempt](https://github.com/hpe-storage/common-host-libs/blob/65eb0171b2ca/linux/device.go#L492-L583): it could not find a matching multipath device with backing paths. `SuccessfulAttachVolume` was a controller-side milestone, not confirmation of a block device, filesystem mount, or ready application.

That distinction matters in a recovery review:

```text
worker Ready → CSI registered → controller publish/attachment
             → node stage/device discovery → node publish/mount → pod Ready
```

The first three observations were present on the destination worker. The chain broke at node staging.

## Two Operations on the Same Volume

I compared the Kubernetes event times with the HPE controller, Nimble storage provider, node-plugin, and worker journals. The controller-side sequence was much more informative than the attachment event alone.

The new worker's publish began at 19:47:15.711. Unpublish from the old worker began at 19:47:15.813, before the new publish had finished. The provider created an access record for the new worker at 19:47:16.202. An unpublish request for **that same volume** to set `online:false` completed at 19:47:16.343. An earlier unpublish attempt had returned an HTTP 500, but the subsequent logged operation succeeded. These are overlapping operations, not a simple sequence in which the old worker fully released the volume before the new worker published it.

An access record and an online volume are separate conditions. The new worker had an access record, and the controller returned publish context, yet the volume could still be unavailable to an iSCSI initiator. The strongest later check was a provider backend GET at 20:19:51: it reported the volume **offline**, with zero iSCSI connections, no sessions, and the new worker's access record still present. That is a logged backend API response, not an independent historical array audit.

This sequence strongly supports an offline-volume explanation for the persistent discovery failure. The old worker's offline operation completed after the new worker's access record was created, and there is no observed intervening operation that put this volume back online before the later check. It does not establish the precise CSI/provider concurrency defect, array semantics, or whether the volume was offline every second between those observations. Those are questions for the storage vendor and the array audit trail.

## The Host Had Another Problem—Briefly

The destination worker's `iscsid` journal also matters. During reboot, it logged `No route to host` for **both** iSCSI target portals from 19:45:38 through 19:47:32. A NIC reporting link up was not proof that the iSCSI routes worked. That transport problem overlapped the first staging attempt and could have contributed to the earliest failures.

But at 19:47:48–51 the same worker discovered two *other* Nimble LUNs and created multipath maps for them. Its retained kernel journal did not show the Alertmanager LUN 0 during the inspected incident window. The temporary routing errors cannot by themselves explain why this particular volume was still reported offline more than 32 minutes after the overlapping publish and unpublish. Nor does the success of a different test volume on another worker prove this volume was online here.

There was a separate UAT issue reaching vCenter over TCP/443 for **VMware CSI**. It was corrected, but this production PVC used **HPE CSI over iSCSI**. The two paths should not be fused into one explanation just because they occurred during the same maintenance effort.

## What Recovery Actually Showed

The operator reported manually restarting the Alertmanager pod. The replacement was scheduled back onto the earlier worker at 20:19:29. At 20:19:52, a new controller publish explicitly brought the backend volume online. Within seconds that worker's kernel logged the expected LUN 0, the CSI plugin found the matching multipath device, XFS mounted cleanly, and the pod became `Ready` at 20:20:00.

The return to the first worker and the new publish coincided with recovery. They do not prove that pod deletion was the only possible repair, or that restarting an arbitrary pod would correct a storage presentation problem. While the volume remained offline, node-stage retries on the second worker would not be expected to make its serial appear. Equally, a forced move of a `ReadWriteOnce` writer is not a general-purpose remedy: the old writer's shutdown and release have to be established before attempting a new placement.

This was one observed incident. The logs support a strong causal chain from overlapping controller operations to an offline backend and failed node discovery, with an early iSCSI routing problem as a plausible additional contributor. They do not supply a vendor-confirmed bug, a reproducible failure rate, or a complete per-second history of the array.

## The Gate I Would Use Next Time

For worker VM maintenance, I would inventory each stateful pod, its PVC and PV, the CSI driver, the current worker, and its `VolumeAttachment` before the first shutdown. After each worker returns, I would wait for the workloads it displaced—not just the worker—to recover before moving to the next VM. In particular:

1. Confirm the old placement and attachment are released before accepting a new writer.
2. Check the new controller attachment **and** the backend volume's online state and intended host access record.
3. Check the destination's CSI registration, iSCSI connectivity, matching LUN/serial and node-stage result, then application `Ready`.
4. Preserve timestamped events, controller/provider/node logs, kernel and `iscsid` journals, and an authorized array audit if serial-based failures persist. Pause further worker moves rather than treating repeated `FailedMount` as normal startup noise.

A useful initial investigation trigger is five minutes without workload readiness after attachment; ten minutes of repeated serial-discovery failures is a reason to stop the maintenance sequence and escalate. Those are proposed observation gates to calibrate locally, not restart timers. The lesson from this case is narrower and more durable: **NodeReady and controller attachment say where recovery has reached. Only device discovery, mount, and workload readiness show that the volume actually made the trip.**
