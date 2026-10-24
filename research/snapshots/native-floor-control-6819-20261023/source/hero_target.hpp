#pragma once
#include "hero_layout.hpp"
#include "hero_composition.hpp"
#include <cstdint>

namespace hero {
// Partial readbacks are diagnostic data only. A refused sample never publishes
// a Target, and these values never authorize or supply a camera pose.
struct TargetDiagnostic {
    int mode=-1;
    unsigned sample=0;
    bool selected_handle_read=false,camera_handle_read=false;
    std::uint32_t selected_handle=0,camera_handle=0;
    const char* resolution="not attempted";
    bool scene_table_read=false,scene_table_in_client=false;
    std::uint32_t scene_table_rva=0;
    const char* scene_type="not sampled";
};
struct Target {
    std::uintptr_t system=0,controller=0,observer=0,services=0,pawn=0,node=0;
    std::uint32_t observer_handle=0,handle=0;
    std::uintptr_t scene_table=0;
    unsigned char mode=0;
    Vec root{};
    Vec world_angles{};
    bool facing_present=false;
    bool same_identity(const Target& other)const{
        return system==other.system && controller==other.controller && observer==other.observer &&
            services==other.services && pawn==other.pawn && node==other.node &&
            observer_handle==other.observer_handle && handle==other.handle && mode==other.mode &&
            scene_table==other.scene_table;
    }
};
// Same-process, read-only sampler. The supplied read function must verify the
// complete byte range. No entity enumeration, fallback offsets or target writes.
template<class Read> class TargetReader {
    std::uintptr_t client_;Read read_;bool include_facing_;
    const char* reason_="not sampled";
    TargetDiagnostic diagnostic_;
    template<class T> bool get(std::uintptr_t at,T& value){return at && read_(at,&value,sizeof(value));}
    bool table(std::uintptr_t at,std::uintptr_t first,std::uintptr_t second=0){
        std::uintptr_t observed{};return get(at,observed) &&
            (observed==client_+first || (second && observed==client_+second));
    }
    bool resolve(std::uintptr_t system,std::uint32_t handle,std::uintptr_t& pawn){
        diagnostic_.resolution="invalid handle";
        if(handle==0xffffffff || handle==0xfffffffe || (handle&0x7fff)>=0x7fff)return false;
        std::uintptr_t chunk{},back{};std::uint32_t actual{};
        diagnostic_.resolution="entity chunk unavailable";
        if(!get(system+8*((handle&0x7fff)>>9),chunk) || !chunk)return false;
        const auto identity=chunk+0x70*(handle&0x1ff);
        diagnostic_.resolution="entity unavailable";
        if(!get(identity,pawn) || !pawn)return false;
        diagnostic_.resolution="entity serial unavailable or mismatched";
        if(!get(identity+0x10,actual) || actual!=handle)return false;
        diagnostic_.resolution="entity identity backlink unavailable or mismatched";
        if(!get(pawn+kEntityIdentity,back) || back!=identity)return false;
        diagnostic_.resolution="ready";return true;
    }
    bool once(std::uintptr_t camera,Target& target){
        reason_="observer identity or services unavailable";
        if(!table(camera,kCameraTable) || !get(client_+kEntityList,target.system) || !target.system ||
           !get(client_+kController,target.controller) || !table(target.controller,kControllerTable) ||
           !get(target.controller+0x6bc,target.observer_handle) || !resolve(target.system,target.observer_handle,target.observer) ||
           !table(target.observer,kObserverPawnTable,kPlayerPawnTable) || !get(target.observer+kObserverServices,target.services) ||
           !table(target.services,kServicesTable,kBaseServicesTable))return false;
        std::uintptr_t methods{},mode_method{},target_method{};std::uint32_t camera_handle{};
        reason_="observer virtual methods differ";
        if(!get(target.services,methods) || !get(methods+0xf0,mode_method) || mode_method!=client_+kGetMode ||
           !get(methods+0x100,target_method) || target_method!=client_+kGetTarget ||
           !get(target.services+0x48,target.mode))return false;
        diagnostic_.mode=target.mode;reason_="observer mode is not an admitted chase candidate";
        if(target.mode!=2 && target.mode!=3)return false;
        reason_="selected observer handle unreadable";
        if(!get(target.services+0x4c,target.handle))return false;
        diagnostic_.selected_handle_read=true;diagnostic_.selected_handle=target.handle;
        reason_="native camera handle unreadable";
        if(!get(camera+0xb0,camera_handle))return false;
        diagnostic_.camera_handle_read=true;diagnostic_.camera_handle=camera_handle;
        reason_="native camera and selected observer handles differ";
        if(camera_handle!=target.handle)return false;
        reason_="selected hero handle resolution failed";
        if(!resolve(target.system,target.handle,target.pawn))return false;
        reason_="selected entity is not the reviewed player pawn type";
        if(!table(target.pawn,kPlayerPawnTable))return false;
        reason_="selected hero scene pointer unreadable";
        if(!get(target.pawn+kSceneNode,target.node))return false;
        reason_="selected hero scene is not a reviewed scene type";
        if(!get(target.node,target.scene_table))return false;
        diagnostic_.scene_table_read=true;
        diagnostic_.scene_table_in_client=target.scene_table>=client_ && target.scene_table-client_<kClientImageSize;
        if(diagnostic_.scene_table_in_client)diagnostic_.scene_table_rva=static_cast<std::uint32_t>(target.scene_table-client_);
        // Exact current-disk zero-offset inheritance and embedded-component
        // construction proof qualifies this third concrete type. Unknown tables
        // still refuse; owner, finite origin and coherent identity remain below.
        if(target.scene_table==client_+kWrappedSkeletonTable)diagnostic_.scene_type="network-wrapped skeleton";
        else if(target.scene_table==client_+kSkeletonTable)diagnostic_.scene_type="base skeleton";
        else if(target.scene_table==client_+kSceneTable)diagnostic_.scene_type="base scene";
        else{diagnostic_.scene_type="unreviewed";return false;}
        reason_="hero scene owner unavailable or mismatched";
        std::uintptr_t owner{};std::array<float,3> root{};
        if(!get(target.node+kNodeOwner,owner) || owner!=target.pawn)return false;
        reason_="hero world position unreadable";
        if(!get(target.node+kAbsoluteOrigin,root))return false;
        for(unsigned n=0;n<3;++n)target.root[n]=root[n];
        reason_="hero world position is nonfinite";
        if(!Finite(target.root))return false;
        if(include_facing_){
            std::array<float,3> angles{};reason_="hero world rotation unreadable";
            if(!get(target.node+kAbsoluteRotation,angles))return false;
            for(unsigned n=0;n<3;++n)target.world_angles[n]=angles[n];
            reason_="hero world rotation is nonfinite";
            if(!Finite(target.world_angles))return false;
            target.facing_present=true;
        }
        return true;
    }
public:
    TargetReader(std::uintptr_t client,Read read,bool include_facing=false):client_(client),read_(read),include_facing_(include_facing){}
    const char* reason()const{return reason_;}
    int observed_mode()const{return diagnostic_.mode;}
    const TargetDiagnostic& diagnostic()const{return diagnostic_;}
    bool sample(std::uintptr_t camera,Target& result){
        diagnostic_={};
        Target a,b;
        diagnostic_.sample=1;
        if constexpr(requires(Read& read){read.begin_pass();})read_.begin_pass();
        if(!once(camera,a))return false;
        // The second sample must supply its own readbacks; never retain a first-
        // sample success flag for a field that becomes unreadable on the second.
        diagnostic_={};diagnostic_.sample=2;
        if constexpr(requires(Read& read){read.begin_pass();})read_.begin_pass();
        if(!once(camera,b))return false;
        if(!a.same_identity(b) || a.root!=b.root || a.world_angles!=b.world_angles){reason_="hero identity or pose changed during sample";return false;}
        result=a;reason_="ready";return true;
    }
};
} // namespace hero
