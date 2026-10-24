#include "hero_target.hpp"
#include <map>
#include <cstring>
#include <cassert>
#include <cstdio>

struct Memory {
    std::map<std::uintptr_t,unsigned char> bytes;
    template<class T>void put(std::uintptr_t at,const T& value){
        const auto* raw=reinterpret_cast<const unsigned char*>(&value);
        for(unsigned n=0;n<sizeof(value);++n)bytes[at+n]=raw[n];
    }
    bool read(std::uintptr_t at,void* output,std::size_t size){
        for(std::size_t n=0;n<size;++n)if(!bytes.count(at+n))return false;
        auto* raw=static_cast<unsigned char*>(output);
        for(std::size_t n=0;n<size;++n)raw[n]=bytes.at(at+n);
        return true;
    }
};
constexpr std::uintptr_t client=0x10000000,entity_system=0x21000000,controller=0x22000000,
    observer=0x23000000,services=0x24000000,pawn=0x25000000,node=0x26000000,chunk=0x27000000,camera=0x28000000;
constexpr std::uint32_t observer_handle=0x1201,target_handle=0x1402;
Memory fixture(){
    Memory m;m.put(client+hero::kEntityList,entity_system);m.put(client+hero::kController,controller);
    m.put(controller,client+hero::kControllerTable);m.put(controller+0x6bc,observer_handle);
    for(auto entry:{std::pair{observer_handle,observer},std::pair{target_handle,pawn}}){
        m.put(entity_system+8*((entry.first&0x7fff)>>9),chunk);
        const auto identity=chunk+0x70*(entry.first&0x1ff);
        m.put(identity,entry.second);m.put(identity+0x10,entry.first);m.put(entry.second+hero::kEntityIdentity,identity);
    }
    m.put(camera,client+hero::kCameraTable);m.put(camera+0xb0,target_handle);
    m.put(observer,client+hero::kObserverPawnTable);m.put(observer+hero::kObserverServices,services);
    m.put(services,client+hero::kServicesTable);
    m.put(client+hero::kServicesTable+0xf0,client+hero::kGetMode);
    m.put(client+hero::kServicesTable+0x100,client+hero::kGetTarget);
    m.put(services+0x48,static_cast<unsigned char>(3));m.put(services+0x4c,target_handle);
    m.put(pawn,client+hero::kPlayerPawnTable);m.put(pawn+hero::kSceneNode,node);
    m.put(node,client+hero::kSkeletonTable);m.put(node+hero::kNodeOwner,pawn);
    m.put(node+hero::kAbsoluteOrigin,std::array<float,3>{100,200,300});return m;
}
int main(){
    auto memory=fixture();auto read=[&](auto at,auto output,auto size){return memory.read(at,output,size);};
    hero::TargetReader reader(client,read);hero::Target target;
    assert(reader.sample(camera,target) && target.handle==target_handle && target.root==hero::Vec({100,200,300}));
    assert(reader.diagnostic().selected_handle_read && reader.diagnostic().camera_handle_read &&
        reader.diagnostic().selected_handle==target_handle && reader.diagnostic().camera_handle==target_handle &&
        reader.diagnostic().sample==2 && reader.observed_mode()==3);
    const auto baseline=target;
    // Current disk constructors publish this legitimate zero-offset derived
    // node. The original two-table reader rejects it before checking the owner.
    memory=fixture();memory.put(node,client+hero::kWrappedSkeletonTable);
    if(!reader.sample(camera,target) || target.root!=hero::Vec({100,200,300}) || target.handle!=target_handle){
        std::fputs("hero_scene_wrapper_regression: valid current-build network-wrapped skeleton rejected before owner/origin validation\n",stderr);
        return 1;
    }
    assert(reader.diagnostic().scene_table_read && reader.diagnostic().scene_table_in_client &&
        reader.diagnostic().scene_table_rva==hero::kWrappedSkeletonTable &&
        std::strcmp(reader.diagnostic().scene_type,"network-wrapped skeleton")==0);
    assert(!target.same_identity(baseline));
    // Admitting the exact wrapper never bypasses the original ownership,
    // identity, finite pose or read boundaries.
    for(unsigned fault=0;fault<5;++fault){
        memory=fixture();memory.put(node,client+hero::kWrappedSkeletonTable);target.handle=0xdead;
        if(fault==0)memory.put(node+hero::kNodeOwner,observer);
        if(fault==1)memory.put(node+hero::kAbsoluteOrigin,std::array<float,3>{NAN,0,0});
        if(fault==2)memory.put(pawn+hero::kEntityIdentity,std::uintptr_t(1));
        if(fault==3)memory.put(node,client+hero::kWrappedSkeletonTable+8);
        if(fault==4)memory.bytes.erase(node+7);
        const auto before=memory.bytes;
        assert(!reader.sample(camera,target) && target.handle==0xdead && memory.bytes==before);
        if(fault==3)assert(reader.diagnostic().scene_table_in_client &&
            reader.diagnostic().scene_table_rva==hero::kWrappedSkeletonTable+8 &&
            std::strcmp(reader.diagnostic().scene_type,"unreviewed")==0);
        if(fault==4)assert(!reader.diagnostic().scene_table_read);
    }
    memory=fixture();memory.put(node,client+hero::kSceneTable);
    assert(reader.sample(camera,target) && std::strcmp(reader.diagnostic().scene_type,"base scene")==0);
    memory=fixture();unsigned scene_reads=0;
    auto changing_scene=[&](auto at,auto output,auto size){
        if(at==node && ++scene_reads==2)memory.put(node,client+hero::kWrappedSkeletonTable);
        return memory.read(at,output,size);
    };
    hero::TargetReader changed_class(client,changing_scene);target.handle=0xdead;
    assert(!changed_class.sample(camera,target) && target.handle==0xdead &&
        std::strcmp(changed_class.reason(),"hero identity or pose changed during sample")==0);
    const std::array<const char*,9> reasons={
        "selected hero handle resolution failed", "selected hero handle resolution failed",
        "hero scene owner unavailable or mismatched", "observer mode is not an admitted chase candidate",
        "native camera and selected observer handles differ", "hero world position is nonfinite",
        "selected entity is not the reviewed player pawn type", "selected hero scene pointer unreadable",
        "observer virtual methods differ"};
    for(unsigned fault=0;fault<9;++fault){
        memory=fixture();target.handle=0xdead;
        if(fault==0)memory.put(chunk+0x70*(target_handle&0x1ff)+0x10,target_handle+0x8000);
        if(fault==1)memory.put(pawn+hero::kEntityIdentity,std::uintptr_t(1));
        if(fault==2)memory.put(node+hero::kNodeOwner,observer);
        if(fault==3)memory.put(services+0x48,static_cast<unsigned char>(4));
        if(fault==4)memory.put(camera+0xb0,target_handle+1);
        if(fault==5)memory.put(node+hero::kAbsoluteOrigin,std::array<float,3>{NAN,0,0});
        if(fault==6)memory.put(pawn,client+hero::kObserverPawnTable);
        if(fault==7)memory.bytes.erase(pawn+hero::kSceneNode+7);
        if(fault==8)memory.put(client+hero::kServicesTable+0x100,client+hero::kGetMode);
        const auto before=memory.bytes;
        assert(!reader.sample(camera,target) && target.handle==0xdead && memory.bytes==before);
        assert(std::strcmp(reader.reason(),reasons[fault])==0);
        if(fault==0)assert(std::strcmp(reader.diagnostic().resolution,"entity serial unavailable or mismatched")==0);
        if(fault==1)assert(std::strcmp(reader.diagnostic().resolution,"entity identity backlink unavailable or mismatched")==0);
        if(fault==4){
            const auto& diagnostic=reader.diagnostic();
            assert(diagnostic.mode==3 && diagnostic.selected_handle_read && diagnostic.camera_handle_read &&
                diagnostic.selected_handle==target_handle && diagnostic.camera_handle==target_handle+1 && diagnostic.sample==1);
        }
    }
    // A raw handle value of zero is distinct from a failed read. Neither a
    // partial value nor an earlier successful sample can publish a valid target.
    memory=fixture();memory.put(services+0x4c,std::uint32_t(0));
    assert(!reader.sample(camera,target) && reader.diagnostic().selected_handle_read &&
        reader.diagnostic().selected_handle==0 && target.handle==0xdead);
    memory=fixture();memory.bytes.erase(services+0x4c);
    assert(!reader.sample(camera,target) && !reader.diagnostic().selected_handle_read &&
        !reader.diagnostic().camera_handle_read && target.handle==0xdead);
    memory=fixture();memory.bytes.erase(camera+0xb0);
    assert(!reader.sample(camera,target) && reader.diagnostic().selected_handle_read &&
        !reader.diagnostic().camera_handle_read && target.handle==0xdead);
    memory=fixture();unsigned selected_reads=0;
    auto second_unreadable=[&](auto at,auto output,auto size){
        if(at==services+0x4c && ++selected_reads==2)return false;
        return memory.read(at,output,size);
    };
    hero::TargetReader second_reader(client,second_unreadable);
    assert(!second_reader.sample(camera,target) && second_reader.diagnostic().sample==2 &&
        !second_reader.diagnostic().selected_handle_read && !second_reader.diagnostic().camera_handle_read &&
        target.handle==0xdead);
    memory=fixture();unsigned origins=0;
    auto changing=[&](auto at,auto output,auto size){
        if(at==node+hero::kAbsoluteOrigin && ++origins==2)memory.put(node+hero::kAbsoluteOrigin,std::array<float,3>{101,200,300});
        return memory.read(at,output,size);
    };
    hero::TargetReader incoherent(client,changing);assert(!incoherent.sample(camera,target));
    memory=fixture();assert(reader.sample(camera,target) && target.same_identity(baseline));
    memory.put(pawn+hero::kSceneNode,std::uintptr_t(0));assert(!reader.sample(camera,target));
    memory=fixture();target.handle=0xdead;
    hero::TargetReader facing(client,read,true);
    assert(!facing.sample(camera,target)&&target.handle==0xdead);
    memory.put(node+hero::kAbsoluteRotation,std::array<float,3>{0,75,0});
    const auto facing_memory=memory.bytes;
    assert(facing.sample(camera,target)&&target.facing_present&&target.world_angles==hero::Vec({0,75,0}));
    assert(target.same_identity(baseline)&&memory.bytes==facing_memory);
    memory.put(node+hero::kAbsoluteRotation,std::array<float,3>{0,NAN,0});target.handle=0xdead;
    assert(!facing.sample(camera,target)&&target.handle==0xdead);
    memory.put(node+hero::kAbsoluteRotation,std::array<float,3>{0,75,0});unsigned angle_reads=0;
    auto angle_change=[&](auto at,auto output,auto size){
        if(at==node+hero::kAbsoluteRotation&&++angle_reads==2)memory.put(at,std::array<float,3>{0,76,0});
        return memory.read(at,output,size);
    };
    hero::TargetReader angle_reader(client,angle_change,true);
    assert(!angle_reader.sample(camera,target)&&target.handle==0xdead);
    memory=fixture();assert(reader.sample(camera,target)&&!target.facing_present); // legacy does not need angle bytes
    std::puts("hero_facing_reader: finite coherent optional world angles, changed/unreadable refusal, unchanged identity and legacy root-only path passed");
    std::puts("hero_target: selected-handle serial/backlink/type/scene-owner/observer-mode/virtual-consumer guards, unreadable and nonfinite data, coherent double sample and no output on refusal passed");
    std::puts("hero_target_diagnostic: exact refusal boundaries, raw zero versus unreadable handles, coherent sample reset and unchanged source memory/output on refusal passed");
    std::puts("hero_scene_wrapper: exact current-build derived node admitted; unknown table, owner, backlink, nonfinite, unreadable and class-transition refusals passed");
}
