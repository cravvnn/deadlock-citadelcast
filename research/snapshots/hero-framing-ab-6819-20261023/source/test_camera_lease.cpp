#include "camera_lease.hpp"
#include <cassert>
#include <vector>
#include <cstdio>

using walker::CameraKey;
using walker::ReleaseKind;
struct NativeManager {
    CameraKey id=1,active=2,retained=3,previous=0;
    walker::ObserverCameraLease lease;
    std::vector<CameraKey> destroyed;
    void select(CameraKey next,bool blend=false) {
        previous=active;active=next;
        if(!blend) finish_transition();
    }
    void finish_transition() {
        if(previous && !lease.retain(id,previous,previous==retained)) destroyed.push_back(previous);
        previous=0;
    }
    void release(bool reviewed=true) {
        auto plan=lease.release(reviewed,active,retained,previous);
        if(plan.kind==ReleaseKind::DestroyOrphan) destroyed.push_back(plan.camera);
    }
    void restore() {
        const auto target=lease.return_target(id,active,4,retained);
        if(target) select(target);
        else if(active==4) select(retained);
        release();
    }
};

int main() {
    // Native selection destroys a non-default original without a scoped lease.
    NativeManager regression;
    regression.select(4);
    assert((regression.destroyed==std::vector<CameraKey>{2}));
    // A completed take returns the same live original and frees only our shot.
    NativeManager complete;
    assert(complete.lease.arm(complete.id,complete.active,complete.retained));
    complete.select(4);
    assert(complete.destroyed.empty() && complete.lease.detached());
    complete.restore();
    assert(complete.active==2 && (complete.destroyed==std::vector<CameraKey>{4}));
    assert(!complete.lease.active());
    // A second take can repeat without retaining a stale claim.
    assert(complete.lease.arm(complete.id,complete.active,complete.retained));
    complete.select(4);complete.restore();
    assert(complete.active==2 && (complete.destroyed==std::vector<CameraKey>{4,4}));
    // Countdown cancellation never took ownership from the native manager.
    NativeManager countdown;
    assert(countdown.lease.arm(1,2,3));countdown.release();
    assert(countdown.active==2 && countdown.destroyed.empty());
    // After a cut, focus/input cancellation uses the same restore contract.
    NativeManager cancel;
    assert(cancel.lease.arm(1,2,3));cancel.select(4);cancel.restore();
    assert(cancel.active==2 && (cancel.destroyed==std::vector<CameraKey>{4}));
    // Never override the operator's subsequent camera; release our orphan once.
    NativeManager operator_change;
    assert(operator_change.lease.arm(1,2,3));operator_change.select(4);operator_change.select(5);
    assert(!operator_change.lease.return_target(1,operator_change.active,4,operator_change.retained));
    operator_change.release();operator_change.release();
    assert(operator_change.active==5 && (operator_change.destroyed==std::vector<CameraKey>{4,2}));
    // An original still referenced as the previous blending camera stays native.
    NativeManager blending;
    assert(blending.lease.arm(1,2,3));blending.select(5,true);blending.release();
    assert(blending.destroyed.empty());blending.finish_transition();
    assert((blending.destroyed==std::vector<CameraKey>{2}));
    // Manager teardown frees our orphan, leaving active-shot teardown native.
    NativeManager manager_exit;
    assert(manager_exit.lease.arm(1,2,3));manager_exit.select(4);manager_exit.release();
    assert((manager_exit.destroyed==std::vector<CameraKey>{2}));
    // An independently observed destruction invalidates return and cleanup.
    NativeManager lost;
    assert(lost.lease.arm(1,2,3));lost.select(4);assert(lost.lease.destroyed(2));
    assert(!lost.lease.return_target(1,4,4,3));lost.release();assert(lost.destroyed.empty());
    // Unknown identity never calls a destructor and refuses another take.
    NativeManager unknown;
    assert(unknown.lease.arm(1,2,3));unknown.select(4);unknown.release(false);
    assert(unknown.destroyed.empty() && unknown.lease.blocked());
    assert(!unknown.lease.arm(1,2,3));
    // A later retained default is honored instead of restoring a stale context.
    NativeManager default_change;
    assert(default_change.lease.arm(1,2,3));default_change.select(4);default_change.retained=6;
    assert(!default_change.lease.return_target(1,4,4,6));default_change.restore();
    assert(default_change.active==6 && (default_change.destroyed==std::vector<CameraKey>{4,2}));
    walker::ObserverCameraLease foreign;
    assert(!foreign.arm(0,2,3));assert(!foreign.arm(1,0,3));assert(foreign.arm(1,2,3));
    assert(!foreign.retain(9,2,false) && !foreign.retain(1,8,false));
    assert(foreign.retain(9,3,true) && !foreign.detached());
    assert(!foreign.return_target(9,4,4,3) && !foreign.destroyed(9));
    std::puts("observer_camera_lease: native destruction regression, return/repeat/cancel, operator override, transition, teardown, lost camera and unknown identity passed");
}
