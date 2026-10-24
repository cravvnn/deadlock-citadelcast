#pragma once
#include <cstdint>

namespace walker {
using CameraKey=std::uintptr_t;
enum class ReleaseKind { None, NativeOwns, DestroyOrphan, Unverified };
struct ReleaseCamera { ReleaseKind kind=ReleaseKind::None; CameraKey camera=0; };

// Mirrors the native manager's explicit retention boundary, not its layout.
// Only a witnessed request to destroy the borrowed original gives us cleanup
// responsibility. Returning or releasing resets the claim BEFORE any callback.
class ObserverCameraLease {
    CameraKey manager_=0,camera_=0,default_=0;
    bool detached_=false,blocked_=false;
public:
    bool active() const { return manager_!=0; }
    bool blocked() const { return blocked_; }
    bool detached() const { return detached_; }
    CameraKey camera() const { return camera_; }
    bool arm(CameraKey manager,CameraKey camera,CameraKey retained) {
        if(active() || blocked_ || !manager || !camera || !retained || camera==retained) return false;
        manager_=manager;camera_=camera;default_=retained;detached_=false;return true;
    }
    bool retain(CameraKey manager,CameraKey camera,bool native_keeps) {
        if(native_keeps) return true;
        if(manager_==manager && camera_ && camera_==camera) {
            detached_=true;return true;
        }
        return false;
    }
    CameraKey return_target(CameraKey manager,CameraKey active,CameraKey owned,CameraKey retained) const {
        return manager_==manager && camera_ && owned && active==owned && retained==default_ ? camera_ : 0;
    }
    bool destroyed(CameraKey camera) {
        if(!camera_ || camera_!=camera) return false;
        camera_=0;detached_=false;return true;
    }
    void mark_unverified() { blocked_=true; }
    ReleaseCamera release(bool reviewed,CameraKey active,CameraKey retained,CameraKey previous) {
        const auto camera=camera_;const bool detached=detached_;
        manager_=0;camera_=0;default_=0;detached_=false;
        if(!camera) return {};
        if(!detached) return {ReleaseKind::NativeOwns,camera};
        if(!reviewed) { blocked_=true;return {ReleaseKind::Unverified,camera}; }
        if(camera==active || camera==retained || camera==previous)
            return {ReleaseKind::NativeOwns,camera};
        return {ReleaseKind::DestroyOrphan,camera};
    }
};
} // namespace walker
