// Independent owned-viewer experiment. Uses this project's pure curve export
// and the separately reviewed build6819 camera interface; no replay bridge.
#include "adapter.hpp"
#include "playback.hpp"
#include "shot_library.hpp"
#include "follow_filter.hpp"
#include "follow_output.hpp"
#include "follow_thread.hpp"
#include "hero_target.hpp"
#include "hero_entry.hpp"
#include "take_archive.hpp"
#include "hero_motion_trace.hpp"
#include "hero_native_phase.hpp"
#include "checked_page_read.hpp"
#include "hero_data_output.hpp"
#include "phase_timing.hpp"
#include "camera_lease.hpp"
#include "take_trace.hpp"
#include "owned_slot.hpp"
#include "pins.hpp"
#include "camera_diagnostics.hpp"
#include "icvar.h"
#include "icommandline.h"
#include "tier0/platform.h"
#include <windows.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <memory>
#include <mutex>
#include <string>

extern std::string CitadelCastHashFile(const char*);
namespace {
std::recursive_mutex mutex;
walker::Playback playback;
enum class Mode { Path, Follow };
Mode mode=Mode::Path;
enum class FollowStyle { Native, Hero };
FollowStyle follow_style=FollowStyle::Native;
hero::EntryRig hero_rig;
hero::HeadingPolicy hero_heading=hero::HeadingPolicy::NativeStart;
hero::TakeArchive take_archive;
double hero_start_yaw=0;
hero_motion::Trace hero_motion_trace;
hero::PhaseCost hero_motion_read_cost;
hero::FreshTargetSampler hero_fresh_target;
hero::PhaseCost hero_native_source_cost;
hero::PhaseCosts hero_cost;
citadelcast_memory::ReadCosts hero_reads,hero_camera_reads;
unsigned failed_gate_mask=0;
double hero_arming_wall_ms=0;
float hero_entry_fov=0;
bool hero_primed=false;
unsigned long long hero_field_updates=0;
hero::Target hero_initial,hero_current;
follow::Pose hero_native{};
const char* hero_target_reason="not sampled";
bool hero_probe_present=false,hero_probe_ready=false;
int hero_probe_mode=-1;
hero::Target hero_probe_target;
hero::TargetDiagnostic hero_probe_diagnostic;
const char* hero_probe_reason="not sampled";
follow::Filter follow_filter;
follow::FramePermit follow_permit;
void* follow_camera{};
std::atomic<DWORD> follow_owner_thread{0};
unsigned long long follow_position_copies=0,follow_angle_copies=0;
double follow_peak_lag=0;
unsigned long long follow_manager_frames=0,follow_native_frames=0,follow_gate_checks=0;
double follow_last_manager=0,follow_max_manager_gap=0,follow_max_gate_ms=0;
const walker::Shot* selected_shot=&walker::kShots[0];
std::uintptr_t client{},engine{},network{};
void* manager{}; void* initial_camera{}; void* owned_camera{};void* initial_default{};
walker::ObserverCameraLease observer_lease;
unsigned long long observer_retentions=0,observer_orphans_destroyed=0;
const char* observer_return="not taken";
walker_trace::Sample native_sample;
walker_trace::Exit camera_exit;
DWORD owner_thread{};
bool aspect_written=false,registered=false,shutting_down=false;
bool aspect_inflight=false,restore_after_write=false,watch_attested=false;
float original_aspect{},last_aspect{};
unsigned long long applied_frames=0;
double last_elapsed=0;
const char* last_result="idle";
const char* binding_failure="not checked";
unsigned binding_slot=0;
int aspect_type=-1,cheats_type=-1;
unsigned long long aspect_flags=0;
bool BindingFailure(const char* reason,unsigned slot=0) { binding_failure=reason;binding_slot=slot;return false; }
std::unique_ptr<CConVarRef<float>> aspect;
std::unique_ptr<CConVarRef<bool>> cheats;
std::array<ConCommandRef,12> commands;
std::array<OwnedSlot,10> hooks;
using Method=void(*)(void*);
using Getter=float*(*)(void*,float*);
std::atomic<Method> original_follow_frame{};
std::atomic<Getter> original_follow_position{},original_follow_angles{};
using Destroy=void*(*)(void*,unsigned);
Method original_manager_frame{},original_data_frame{},original_deactivate{};
Destroy original_manager_destroy{},original_data_destroy{},original_observer_destroy{};
using Keep=bool(*)(void*,void*);
Keep original_manager_keep{};
walker::CameraKey Key(void* object) { return reinterpret_cast<walker::CameraKey>(object); }

template<class T> T& Field(void* object,std::size_t offset) { return *reinterpret_cast<T*>(static_cast<unsigned char*>(object)+offset); }
template<class T> T VFunc(void* object,unsigned slot) { return reinterpret_cast<T>((*reinterpret_cast<void***>(object))[slot]); }
double Now() {
    LARGE_INTEGER ticks{},frequency{};
    if(!QueryPerformanceFrequency(&frequency) || !QueryPerformanceCounter(&ticks) || frequency.QuadPart<=0) return NAN;
    return static_cast<double>(ticks.QuadPart)/static_cast<double>(frequency.QuadPart);
}
bool ReadHeroBytes(std::uintptr_t at,void* output,std::size_t size) {
    citadelcast_memory::CheckedRead read;read.begin_pass();return read(at,output,size);
}
bool ReadHeroTarget(void* camera,hero::Target& target,bool facing) {
    const bool measure=mode==Mode::Follow && follow_style==FollowStyle::Hero && playback.active();
    const double began=measure?Now():0;
    hero::TargetReader reader(client,citadelcast_memory::CheckedRead(measure?&hero_reads:nullptr),facing);
    const bool ready=reader.sample(reinterpret_cast<std::uintptr_t>(camera),target);
    if(measure)hero_cost.target.add(began,Now());
    hero_target_reason=reader.reason();return ready;
}
bool ReadHeroTarget(void* camera,hero::Target& target){return ReadHeroTarget(camera,target,hero_heading!=hero::HeadingPolicy::NativeStart);}
bool HeroNativeRoute(){return mode==Mode::Follow && follow_style==FollowStyle::Hero;}
const char* ShotId(){return mode==Mode::Follow?(follow_style==FollowStyle::Hero?"hero-three-quarter":"native-chase-filter"):selected_shot->id;}
bool FollowActive(){return follow_style==FollowStyle::Hero?hero_rig.active():follow_filter.active();}
const follow::Pose& FollowNative(){return follow_style==FollowStyle::Hero?hero_native:follow_filter.native();}
const follow::Pose& FollowOutput(){return follow_style==FollowStyle::Hero?hero_rig.pose():follow_filter.pose();}
bool Foreground() {
    DWORD pid{}; HWND window=GetForegroundWindow();
    return window && GetWindowThreadProcessId(window,&pid) && pid==GetCurrentProcessId();
}
bool InputIdle() {
    constexpr std::array<int,13> keys={'W','A','S','D',VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,VK_SHIFT,VK_CONTROL,VK_ESCAPE,VK_LBUTTON,VK_RBUTTON};
    for(int key:keys)
        if(GetAsyncKeyState(key)&0x8000) return false;
    return true;
}
bool ModulesPresent() {
    return client && engine && reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"client.dll"))==client
        && reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"engine2.dll"))==engine
        && network && reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"networksystem.dll"))==network;
}
bool RuntimeBindings() {
    if(!ModulesPresent()) return BindingFailure("module handle identity changed");
    for(const auto& pin:kManagerSlotPins) {
        auto cell=reinterpret_cast<void**>(client+kManagerTable)+pin.slot;
        bool ours=false;for(const auto& hook:hooks) if(hook.installed && hook.cell==cell && *cell==hook.after) ours=true;
        if(!ours && reinterpret_cast<std::uintptr_t>(*cell)!=client+pin.method) return BindingFailure("manager camera table entry differs",pin.slot);
    }
    for(const auto& pin:kDataSlotPins) {
        auto cell=reinterpret_cast<void**>(client+kDataTable)+pin.slot;
        bool ours=false;for(const auto& hook:hooks) if(hook.installed && hook.cell==cell && *cell==hook.after) ours=true;
        if(!ours && reinterpret_cast<std::uintptr_t>(*cell)!=client+pin.method) return BindingFailure("data camera table entry differs",pin.slot);
    }
    for(const auto& pin:kObserverSlotPins) {
        auto cell=reinterpret_cast<void**>(client+kObserverTable)+pin.slot;
        bool ours=false;for(const auto& hook:hooks) if(hook.installed && hook.cell==cell && *cell==hook.after) ours=true;
        if(!ours && reinterpret_cast<std::uintptr_t>(*cell)!=client+pin.method) return BindingFailure("observer camera table entry differs",pin.slot);
    }
    auto engine_table=reinterpret_cast<std::uintptr_t*>(engine+0x4e2790);
    if(engine_table[39]!=engine+kFullyConnected) return BindingFailure("engine connection table entry differs",39);
    if(engine_table[88]!=engine+0x73690) return BindingFailure("engine aspect table entry differs",88);
    binding_failure="none";binding_slot=0;return true;
}
bool ViewerReady() {
    // Read the same cached BROADCAST channel label printed by status. This
    // sends no requests and says nothing about source-server cheats/security.
    if(!ModulesPresent() || !cheats || cheats->Get() ||
        !reinterpret_cast<bool(*)()>(engine+kFullyConnected)()) return false;
    void* game_client=*reinterpret_cast<void**>(engine+kNetworkClientGlobal);
    if(!game_client) return false;
    void* channel=Field<void*>(game_client,0xf0);
    if(!channel || Field<std::uintptr_t>(channel,0)!=network+kChannelTable ||
        VFunc<std::uintptr_t>(channel,1)!=network+kChannelStatusLabel) return false;
    const char* label=VFunc<const char*(*)(void*)>(channel,1)(channel);
    return label && std::strncmp(label,"BROADCAST",10)==0;
}
bool ManagerValid() {
    return ModulesPresent() && manager && Field<std::uintptr_t>(manager,0)==client+kManagerTable;
}
bool HasTable(void* object,std::uintptr_t table) {
    void* actual{};
    return ModulesPresent() && object && walker_diagnostic::ReadPointer(object,actual,
        HeroNativeRoute()&&playback.active()?&hero_camera_reads:nullptr) &&
        reinterpret_cast<std::uintptr_t>(actual)==client+table;
}
bool ObserverSelectionReady(void* object) {
    if(!HasTable(object,kManagerTable)) return false;
    void* active=Field<void*>(object,0x28);void* retained=Field<void*>(object,0x20);
    return active && active!=retained && HasTable(active,kObserverTable) && HasTable(retained,kRetainedTable) &&
        !Field<void*>(object,0x30) && !Field<unsigned char>(object,0x38);
}
using CameraSnapshot=walker_diagnostic::Snapshot;
CameraSnapshot ObserveCamera() {
    if(!ModulesPresent()) return {};
    auto get=reinterpret_cast<void*(*)(int)>(client+kGetManager);
    return walker_diagnostic::ObserveCamera(get(-1),get(0),client,kManagerTable);
}
void Status(const CameraSnapshot* snapshot=nullptr) {
    HMODULE self{}; char path[32768]{};
    if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCSTR>(&RegisterWalkerCommands),&self) || !GetModuleFileNameA(self,path,sizeof(path))) return;
    const std::string target=std::string(path)+".walker-status.json",temp=target+".tmp";
    FILE* out{}; if(fopen_s(&out,temp.c_str(),"wb")!=0) return;
    std::fprintf(out,"{\"pid\":%lu,\"build\":6819,\"phase\":%d,\"result\":\"%s\",\"shot_id\":\"%s\",\"duration\":%.9f,\"frames\":%llu,\"last_elapsed\":%.9f,\"aspect_restore_pending\":%s,\"watch_operator_attested\":%s,\"live_verified\":false",
        GetCurrentProcessId(),static_cast<int>(playback.phase()),last_result,ShotId(),playback.duration(),applied_frames,last_elapsed,aspect_written?"true":"false",watch_attested?"true":"false");
    std::fprintf(out,",\"take_id\":%llu,\"hero_profile\":\"%s\",\"hero_start_yaw\":%.9g,\"hero_current_yaw\":%.9g,\"hero_goal_bearing\":%.9g",
        static_cast<unsigned long long>(take_archive.id()),hero::Profile(hero_heading),hero_start_yaw,hero_current.world_angles[1],hero_rig.bearing());
    std::fprintf(out,",\"test_mode\":\"%s\",\"follow_response\":0.25,\"follow_sample_present\":%s,\"follow_native\":[",mode==Mode::Follow?(follow_style==FollowStyle::Hero?"target-focused hero native data camera":"native chase pose filter"):"saved path",applied_frames && mode==Mode::Follow?"true":"false");
    for(unsigned n=0;n<6;++n)std::fprintf(out,"%s%.9g",n?",":"",FollowNative()[n]);
    std::fputs("],\"follow_output\":[",out);
    for(unsigned n=0;n<6;++n)std::fprintf(out,"%s%.9g",n?",":"",FollowOutput()[n]);
    std::fputs("]",out);
    std::fprintf(out,",\"follow_position_copies\":%llu,\"follow_angle_copies\":%llu,\"follow_peak_lag\":%.9g",follow_position_copies,follow_angle_copies,follow_peak_lag);
    std::fprintf(out,",\"follow_manager_frames\":%llu,\"follow_native_frames\":%llu,\"follow_gate_checks\":%llu,\"follow_max_manager_gap\":%.9g,\"follow_max_gate_ms\":%.9g",follow_manager_frames,follow_native_frames,follow_gate_checks,follow_max_manager_gap,follow_max_gate_ms);
    if(mode==Mode::Follow && follow_style==FollowStyle::Hero){
        std::fprintf(out,",\"hero_target_handle\":%u,\"hero_target_reason\":\"%s\",\"hero_recenters\":%llu,\"hero_focus\":[%.9g,%.9g,%.9g],\"hero_root\":[%.9g,%.9g,%.9g]",hero_current.handle,hero_target_reason,hero_rig.recenters(),hero_rig.focus()[0],hero_rig.focus()[1],hero_rig.focus()[2],hero_current.root[0],hero_current.root[1],hero_current.root[2]);
        std::fprintf(out,",\"hero_output_route\":\"owned data camera\",\"hero_entry_fov\":%.9g,\"hero_primed_before_select\":%s,\"hero_field_updates\":%llu,\"hero_phase_costs\":",hero_entry_fov,hero_primed?"true":"false",hero_field_updates);
        hero_cost.write(out);
        std::fputs(",\"hero_read_costs\":",out);hero_reads.write(out);
        std::fputs(",\"camera_read_costs\":",out);hero_camera_reads.write(out);
        std::fprintf(out,",\"failed_gate_mask\":%u",failed_gate_mask);
        std::fprintf(out,",\"hero_arming_wall_ms\":%.9g",hero_arming_wall_ms);
        std::fprintf(out,",\"hero_entry_transition\":{\"duration\":1,\"elapsed\":%.9g,\"entry_frames\":%llu,\"minimum_horizontal_radius\":%.9g,\"max_position_step\":%.9g,\"max_angle_step\":%.9g,\"native_entry\":[",hero_rig.entry_elapsed(),hero_rig.entry_frames(),hero_rig.min_radius(),hero_rig.max_position_step(),hero_rig.max_angle_step());
        const auto& entry=hero_rig.native_entry();for(unsigned n=0;n<6;++n)std::fprintf(out,"%s%.9g",n?",":"",entry[n]);
        std::fputs("]}",out);
        std::fputs(",\"hero_motion_read_cost\":{",out);hero_motion_read_cost.write(out,"sample_wall");std::fputs("}",out);
        std::fputs(",\"hero_motion_trace\":",out);hero_motion_trace.write(out,!playback.active());
        std::fprintf(out,",\"hero_native_source\":{\"refreshes\":%llu,\"samples\":%llu,\"refused\":%llu,\"reason\":\"%s\",",
            hero_fresh_target.refreshes,hero_fresh_target.samples,hero_fresh_target.refused,hero_fresh_target.reason());
        hero_native_source_cost.write(out,"native_getter_wall");std::fputs("}",out);
    }
    if(hero_probe_present)std::fprintf(out,",\"hero_probe_facing\":{\"present\":%s,\"world_angles\":[%.9g,%.9g,%.9g]}",hero_probe_target.facing_present?"true":"false",hero_probe_target.world_angles[0],hero_probe_target.world_angles[1],hero_probe_target.world_angles[2]);
    if(hero_probe_present)std::fprintf(out,",\"hero_probe\":{\"ready\":%s,\"reason\":\"%s\",\"observer_mode\":%d,\"handle\":%u,\"root\":[%.9g,%.9g,%.9g],\"diagnostic\":{\"sample\":%u,\"selected_handle_read\":%s,\"selected_handle\":%u,\"camera_handle_read\":%s,\"camera_handle\":%u,\"last_handle_resolution\":\"%s\",\"scene_table_read\":%s,\"scene_table_in_client\":%s,\"scene_table_rva\":%u,\"scene_type\":\"%s\"},\"camera_or_setting_writes\":false}",hero_probe_ready?"true":"false",hero_probe_reason,hero_probe_mode,hero_probe_target.handle,hero_probe_target.root[0],hero_probe_target.root[1],hero_probe_target.root[2],hero_probe_diagnostic.sample,hero_probe_diagnostic.selected_handle_read?"true":"false",hero_probe_diagnostic.selected_handle,hero_probe_diagnostic.camera_handle_read?"true":"false",hero_probe_diagnostic.camera_handle,hero_probe_diagnostic.resolution,hero_probe_diagnostic.scene_table_read?"true":"false",hero_probe_diagnostic.scene_table_in_client?"true":"false",hero_probe_diagnostic.scene_table_rva,hero_probe_diagnostic.scene_type);
    std::fprintf(out,",\"observer_lease_active\":%s,\"observer_retention_seen\":%s,\"observer_cleanup_unverified\":%s,\"observer_retentions\":%llu,\"observer_orphans_destroyed\":%llu,\"observer_return\":\"%s\"",
        observer_lease.active()?"true":"false",observer_lease.detached()?"true":"false",observer_lease.blocked()?"true":"false",observer_retentions,observer_orphans_destroyed,observer_return);
    walker_trace::Write(out,native_sample,camera_exit);
    if(snapshot) {
        const auto& d=*snapshot;
        std::fprintf(out,",\"camera_snapshot\":{\"kind\":\"operator status only\",\"manager_present\":%s,\"manager_readable\":%s,\"manager_reviewed\":%s,\"slot0_same\":%s,\"active_present\":%s,\"retained_present\":%s,\"active_default\":%s,\"transition_present\":%s,\"manager_type\":\"%s\",\"active_type\":\"%s\",\"retained_type\":\"%s\",\"manager_table_rva\":%llu,\"active_table_rva\":%llu,\"retained_table_rva\":%llu}",
            d.manager_present?"true":"false",d.manager_readable?"true":"false",d.manager_reviewed?"true":"false",d.slot0_same?"true":"false",d.active_present?"true":"false",d.retained_present?"true":"false",d.active_default?"true":"false",d.transition_present?"true":"false",d.manager_type,d.active_type,d.retained_type,
            static_cast<unsigned long long>(d.manager_table),static_cast<unsigned long long>(d.active_table),static_cast<unsigned long long>(d.retained_table));
    }
    std::fputs("}\n",out);
    const bool written=std::ferror(out)==0;const int closed=std::fclose(out);
    if(!written || closed!=0 || !MoveFileExA(temp.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return;
    take_archive.publish([&](auto id){
        const auto saved=std::string(path)+".take-"+std::to_string(id)+".json";
        return CopyFileA(target.c_str(),saved.c_str(),TRUE)!=0;
    });
}
void RestoreAspect() {
    if(aspect_inflight) { restore_after_write=true;return; }
    if(!aspect_written || !aspect) return;
    const float current=aspect->Get();
    if(walker::MayRestoreAspect(current,last_aspect,aspect_written)) {
        if(aspect->IsFlagSet(FCVAR_PERFORMING_CALLBACKS)) { last_result="aspect restoration pending";Status();return; }
        aspect->Set(original_aspect);
        if(aspect->Get()!=original_aspect) { last_result="aspect restoration not immediate"; Status(); return; }
    } else {
        Msg("CitadelCast kept the operator's later r_aspectratio value.\n");
    }
    aspect_written=false;
}
bool NativeCameraAccessSafe() {
    return owner_thread==GetCurrentThreadId() && ManagerValid() && RuntimeBindings();
}
void ReleaseObserverLease() {
    const bool reviewed=NativeCameraAccessSafe();
    const auto release=observer_lease.release(reviewed,
        reviewed?Key(Field<void*>(manager,0x28)):0,
        reviewed?Key(Field<void*>(manager,0x20)):0,
        reviewed?Key(Field<void*>(manager,0x30)):0);
    initial_camera=nullptr;initial_default=nullptr;manager=nullptr;
    if(release.kind==walker::ReleaseKind::DestroyOrphan) {
        void* orphan=reinterpret_cast<void*>(release.camera);
        if(owner_thread==GetCurrentThreadId() && original_observer_destroy && RuntimeBindings() && HasTable(orphan,kObserverTable)) {
            // The lease is already empty: destructor callbacks cannot release twice.
            ++observer_orphans_destroyed;original_observer_destroy(orphan,1);
        } else { observer_lease.mark_unverified();observer_return="observer cleanup unverified"; }
    } else if(release.kind==walker::ReleaseKind::Unverified) observer_return="observer cleanup unverified";
}
void Stop(const char* reason,bool return_observer) {
    if(take_archive.pending()){Status();return;} // preserve the unsaved completed take
    follow_owner_thread.store(0,std::memory_order_release);
    follow_permit.invalidate();
    follow_filter.stop(reason);follow_camera=nullptr;
    hero_rig.stop(reason);
    hero_motion_trace.stop();
    if(mode==Mode::Follow)observer_return="native chase preserved; filter disabled";
    playback.cancel(reason);last_result=reason;
    RestoreAspect();
    void* old=owned_camera;owned_camera=nullptr;
    if(return_observer && old) {
        observer_return="observer restoration unavailable";
        if(NativeCameraAccessSafe()) {
            if(Field<void*>(manager,0x28)==old) {
                void* target=reinterpret_cast<void*>(observer_lease.return_target(Key(manager),Key(old),Key(old),Key(Field<void*>(manager,0x20))));
                if(HasTable(target,kObserverTable)) {
                    observer_return="original observer selection requested";
                    VFunc<void(*)(void*,void*)>(manager,10)(manager,target);
                } else if(HasTable(Field<void*>(manager,0x20),kRetainedTable)) {
                    observer_return="native fallback selection requested";
                    VFunc<Method>(manager,11)(manager);
                }
            } else observer_return="later camera selection preserved";
        }
    } else if(old) observer_return="native camera transition not overridden";
    ReleaseObserverLease();take_archive.finish();Status();
    Msg("CitadelCast Walker: %s. Observer: %s.\n",reason,observer_return);
}
walker::Gates Gates() {
    const bool measure=mode==Mode::Follow && playback.active();
    const double began=measure?Now():0;
    walker::Gates g;
    g.identity=!shutting_down && owner_thread==GetCurrentThreadId() && ManagerValid() && RuntimeBindings() &&
        observer_lease.active() && observer_lease.camera()==Key(initial_camera) && HasTable(initial_camera,kObserverTable);
    g.foreground=Foreground();g.viewer=ViewerReady();g.input_idle=InputIdle();
    if(g.identity) {
        void* previous=Field<void*>(manager,0x30);
        g.camera=Field<void*>(manager,0x28)==(owned_camera?owned_camera:initial_camera) &&
            Field<void*>(manager,0x20)==initial_default && HasTable(initial_default,kRetainedTable) &&
            (!previous || (owned_camera && previous==initial_camera));
    } else g.camera=false;
    if(measure){
        if(!g.valid()&&!failed_gate_mask)failed_gate_mask=(!g.identity?1u:0u)|(!g.foreground?2u:0u)|(!g.viewer?4u:0u)|(!g.input_idle?8u:0u)|(!g.camera?16u:0u);
        ++follow_gate_checks;const double ended=Now();if(std::isfinite(began) && std::isfinite(ended) && ended>=began)follow_max_gate_ms=(std::max)(follow_max_gate_ms,1000*(ended-began));if(HeroNativeRoute())(playback.phase()!=walker::Phase::Countdown?hero_cost.gates:hero_cost.countdown_gates).add(began,ended);
    }
    return g;
}
bool WriteHeroOwnedPose(void* camera,bool before_selection=false){
    const double began=Now();
    const bool owned=HeroNativeRoute() && playback.active() && camera && camera==owned_camera &&
        owner_thread==GetCurrentThreadId() && ManagerValid() && HasTable(camera,kDataTable) &&
        Field<void*>(manager,0x28)==(before_selection?initial_camera:camera) &&
        Field<void*>(manager,0x20)==initial_default && hero_rig.active();
    float* output=camera?reinterpret_cast<float*>(static_cast<unsigned char*>(camera)+0x38):nullptr;
    const bool wrote=hero::WriteNativePose(output,hero_rig.pose(),hero_entry_fov,owned);
    if(wrote){++hero_field_updates;if(before_selection)hero_primed=true;}
    hero_cost.publish.add(began,Now());return wrote;
}
void DataFrame(void* camera) {
    std::lock_guard lock(mutex);
    const bool measure=HeroNativeRoute() && camera==owned_camera && playback.active();
    const double native_began=measure?Now():0;
    original_data_frame(camera);
    if(measure)hero_cost.native_data.add(native_began,Now());
    if(camera!=owned_camera || !playback.active()) return;
    if(HeroNativeRoute()){
        ++follow_native_frames;
        if(!Gates().valid() || !HasTable(camera,kDataTable)){
            playback.cancel("hero owned camera/input gate changed");last_result="hero owned camera/input gate changed";return;
        }
        if(Field<unsigned char>(camera,0x7c)){
            playback.cancel("hero native scaffold finished early");last_result="hero native scaffold finished early";return;
        }
        hero::Target target;
        if(!hero_fresh_target.sample(hero_initial,target,[camera]{
                return playback.active() && HeroNativeRoute() && camera==owned_camera &&
                    Gates().valid() && HasTable(camera,kDataTable);
            },
            [](hero::Target& out){return ReadHeroTarget(initial_camera,out);},
            [](const hero::Target& source){
                // Validate pawn/node/owner/serial before this native cache refresh.
                // Accept only its exact expected address, then resample via checked reads.
                const double began=Now();
                const auto result=reinterpret_cast<std::uintptr_t(*)(void*)>(client+kHeroAbsoluteOriginGetter)
                    (reinterpret_cast<void*>(source.pawn));
                hero_native_source_cost.add(began,Now());
                return result==source.node+hero::kAbsoluteOrigin;
            })){
            hero_rig.stop(hero_fresh_target.reason());last_result=hero_rig.reason();playback.cancel(last_result);return;
        }
        hero_current=target;
        const double now=Now(),began=now;
        const bool advanced=hero_rig.advance(now,target.root,true,target.world_angles[1]);
        hero_cost.compose.add(began,Now());
        if(!advanced){last_result=hero_rig.reason();playback.cancel(last_result);return;}
        if(!WriteHeroOwnedPose(camera)){
            hero_rig.stop("hero owned pose publication refused");last_result=hero_rig.reason();playback.cancel(last_result);return;
        }
        follow_peak_lag=(std::max)(follow_peak_lag,hero_rig.lag());
        ++applied_frames;last_elapsed=playback.elapsed(now);return;
    }
    if(owner_thread==GetCurrentThreadId() && RuntimeBindings() && HasTable(camera,kDataTable)) {
        native_sample.present=true;native_sample.elapsed=playback.elapsed(Now());
        native_sample.native_start=Field<float>(camera,0x2c);
        native_sample.native_now=VFunc<float(*)(void*)>(camera,52)(camera);
        native_sample.key_index=Field<int>(camera,0xa8);
        native_sample.finished=Field<unsigned char>(camera,0x7c)!=0;
        for(unsigned n=0;n<native_sample.pose.size();++n)
            native_sample.pose[n]=Field<float>(camera,0x38+n*4);
    }
    if(!Gates().valid() || (aspect_written && aspect->Get()!=last_aspect)) {
        // Caller is still inside the manager update. Queue restoration at its
        // outer boundary so this callback never destroys its current camera.
        playback.cancel("camera/input/framing gate changed");return;
    }
    const double now=Now(),elapsed=playback.elapsed(now);
    if(!std::isfinite(now) || elapsed<last_elapsed) { playback.cancel("invalid frame clock");return; }
    const auto p=walker::EvaluateShot(*selected_shot,elapsed);
    const float requested=static_cast<float>(p[walker::Aspect]);
    if(aspect->IsFlagSet(FCVAR_PERFORMING_CALLBACKS)) { playback.cancel("aspect callback busy");return; }
    aspect_inflight=true;
    aspect->Set(requested);
    aspect_inflight=false;
    const float actual=aspect->Get();
    if(actual==requested) { last_aspect=requested;aspect_written=true; }
    if(restore_after_write) { restore_after_write=false;RestoreAspect();return; }
    // A cvar callback may itself change the observer camera. Do not access the
    // former object after that callback has invalidated our camera ownership.
    if(camera!=owned_camera || !playback.active()) return;
    if(actual!=requested || !Gates().valid()) { playback.cancel("aspect/input gate changed");return; }
    for(unsigned n=0;n<3;++n) Field<float>(camera,0x38+n*4)=static_cast<float>(p[n]);
    for(unsigned n=0;n<3;++n) Field<float>(camera,0x44+n*4)=static_cast<float>(p[walker::Pitch+n]);
    Field<float>(camera,0x50)=static_cast<float>(walker::VerticalFov(p));
    ++applied_frames;last_elapsed=elapsed;
}
void CaptureExit(const char* event) {
    if(camera_exit.present) return;
    HMODULE self{};
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCSTR>(&RegisterWalkerCommands),&self);
    const auto snapshot=ObserveCamera();
    camera_exit=walker_trace::Capture(event,snapshot.active_type,client,engine,reinterpret_cast<std::uintptr_t>(self));
}
bool ReadNativeFollowPose(void* camera,follow::Pose& pose) {
    float position[3]{},angles[3]{};
    const auto get_position=original_follow_position.load(),get_angles=original_follow_angles.load();
    if(!get_position || !get_angles || get_position(camera,position)!=position || get_angles(camera,angles)!=angles)return false;
    for(unsigned n=0;n<3;++n){pose[n]=position[n];pose[n+3]=angles[n];}
    return follow::Finite(pose);
}
bool FollowOutputAllowed(void* camera) {
    // The owner thread already checked full gates for the current sample.
    // Cheap selection checks close same-thread native selection changes; the
    // permit also enforces freshness and native-update pass-through.
    return mode==Mode::Follow && follow_style==FollowStyle::Native && playback.active() && applied_frames && camera==follow_camera &&
        FollowActive() && manager && initial_camera==camera &&
        Field<void*>(manager,0x28)==camera && Field<void*>(manager,0x20)==initial_default &&
        !Field<void*>(manager,0x30) && !Field<unsigned char>(manager,0x38);
}
float* FollowPosition(void* camera,float* output) {
    return follow::ReadOnOwner(follow_owner_thread,mutex,
        [&]{return original_follow_position.load()(camera,output);},
        [&](float* result){if(result==output && follow_permit.copy(follow_filter,result,0,FollowOutputAllowed(camera),Now()))++follow_position_copies;});
}
float* FollowAngles(void* camera,float* output) {
    return follow::ReadOnOwner(follow_owner_thread,mutex,
        [&]{return original_follow_angles.load()(camera,output);},
        [&](float* result){if(result==output && follow_permit.copy(follow_filter,result,3,FollowOutputAllowed(camera),Now()))++follow_angle_copies;});
}
void FollowFrame(void* camera) {
    const auto native=original_follow_frame.load();
    if(follow_owner_thread.load(std::memory_order_acquire)!=GetCurrentThreadId()){native(camera);return;}
    std::lock_guard lock(mutex);
    {follow::FramePermit::NativeUpdate raw(follow_permit);native(camera);}
    if(mode!=Mode::Follow || camera!=follow_camera || !playback.active())return;
    ++follow_native_frames;
    follow::Pose pose{};const double now=Now();
    if(!follow_permit.refresh(now,[]{return Gates().valid();}) || !ReadNativeFollowPose(camera,pose)){
        follow_permit.invalidate();
        follow_filter.stop("follow native pose/gate changed");last_result=follow_filter.reason();playback.cancel(last_result);return;
    }
    if(!follow_filter.advance(now,pose,true)){follow_permit.invalidate();last_result=follow_filter.reason();playback.cancel(last_result);return;}
    follow_peak_lag=(std::max)(follow_peak_lag,follow::Distance(follow_filter.native(),follow_filter.pose()));
    ++applied_frames;last_elapsed=playback.elapsed(now);
}
void Deactivate(void* camera) {
    std::lock_guard lock(mutex);
    if(camera==owned_camera) { CaptureExit("owned camera deactivated");Stop("observer camera changed",false); }
    original_deactivate(camera);
}
void* DataDestroy(void* camera,unsigned flags) {
    std::lock_guard lock(mutex);
    if(camera==owned_camera) { CaptureExit("owned camera destroyed");Stop("owned camera destroyed",false); }
    return original_data_destroy(camera,flags);
}
bool KeepCamera(void* object,void* camera) {
    std::lock_guard lock(mutex);
    const bool native_keeps=original_manager_keep(object,camera);
    const bool before=observer_lease.detached();
    const bool keep=observer_lease.retain(Key(object),Key(camera),native_keeps);
    if(!before && observer_lease.detached()) ++observer_retentions;
    return keep;
}
void* ObserverDestroy(void* camera,unsigned flags) {
    std::lock_guard lock(mutex);
    if(observer_lease.destroyed(Key(camera))) {
        initial_camera=nullptr;playback.cancel("original observer destroyed");
        last_result="original observer destroyed";observer_return="original observer lost";Status();
    }
    return original_observer_destroy(camera,flags);
}
void* ManagerDestroy(void* object,unsigned flags) {
    std::lock_guard lock(mutex);
    if(object==manager) Stop("camera manager destroyed",false);
    return original_manager_destroy(object,flags);
}
bool BeginCamera();
bool BeginHeroCamera();
bool BeginFollow() {
    if(HeroNativeRoute())return BeginHeroCamera();
    follow_permit.invalidate();
    follow::Pose pose{};
    if(!Gates().valid() || !ObserverSelectionReady(manager) || !ReadNativeFollowPose(initial_camera,pose))return false;
    const double now=Now();
    if(!follow_filter.begin(now,pose))return false;
    if(!playback.begin_ready(now))return false;
    follow_camera=initial_camera;follow_owner_thread.store(owner_thread,std::memory_order_release);
    observer_return="native chase retained";last_result="playing";Status();
    Msg("CitadelCast Follow:%s,12seconds,0.25-second response; native lens retained,open-area test only.\n",follow_style==FollowStyle::Hero?"target-focused three-quarter hero shot":"native chase pose filter");
    return true;
}
void CaptureMotionPoint(hero_motion::Row& row,bool after){
    // Caller checked full current owner/viewer/input/selection gates. This
    // sampler supplies diagnostics only, never a camera pose or fallback target.
    const double began=Now();
    hero::TargetReader reader(client,citadelcast_memory::CheckedRead{});hero::Target target;
    const bool ready=reader.sample(reinterpret_cast<std::uintptr_t>(initial_camera),target)&&target.same_identity(hero_initial);
    unsigned flags=static_cast<unsigned>(row[2]);
    if(ready){flags|=after?2u:1u;for(unsigned n=0;n<3;++n)row[(after?6:3)+n]=target.root[n];}
    void* camera=Field<void*>(manager,0x28);
    if((camera==owned_camera&&HasTable(camera,kDataTable))||(camera==initial_camera&&HasTable(camera,kObserverTable))){
        float position[3]{},angles[3]{};
        if(VFunc<Getter>(camera,12)(camera,position)==position&&VFunc<Getter>(camera,15)(camera,angles)==angles){
            follow::Pose pose{};for(unsigned n=0;n<3;++n){pose[n]=position[n];pose[n+3]=angles[n];}
            if(follow::Finite(pose)){flags|=after?8u:4u;for(unsigned n=0;n<6;++n)row[(after?15:9)+n]=pose[n];}
        }
    }
    row[2]=flags;hero_motion_read_cost.add(began,Now());
}
void ManagerFrame(void* object) {
    std::lock_guard lock(mutex);
    walker::Tick tick;
    hero_motion::Row motion{};bool trace_frame=false;
    const auto frames_before=applied_frames;
    const bool ours=object==manager;
    if(ours && playback.active()) {
        const double now=Now();
        if(mode==Mode::Follow){
            follow_permit.invalidate();++follow_manager_frames;
            if(follow_last_manager && std::isfinite(now) && now>=follow_last_manager)follow_max_manager_gap=(std::max)(follow_max_manager_gap,now-follow_last_manager);
            if(HeroNativeRoute() && follow_last_manager)(playback.phase()!=walker::Phase::Countdown?hero_cost.playing_gap:hero_cost.countdown_gap).add(follow_last_manager,now);
            follow_last_manager=now;
        }
        const auto gates=Gates();
        if(HeroNativeRoute()&&gates.valid()){
            motion[0]=now;motion[1]=static_cast<int>(playback.phase());
            CaptureMotionPoint(motion,false);trace_frame=true;
        }
        tick=playback.step(now,gates);
        if(tick.action==walker::Action::Cancel || tick.action==walker::Action::Complete)
            Stop(tick.action==walker::Action::Complete?"complete":tick.reason,true);
    }
    const bool measure=ours && HeroNativeRoute() && playback.active();
    const bool playing=playback.phase()!=walker::Phase::Countdown;
    const double native_began=measure?Now():0;
    {follow::FramePermit::NativeUpdate raw(follow_permit);original_manager_frame(object);}
    if(measure)(playing?hero_cost.native_manager:hero_cost.countdown_manager).add(native_began,Now());
    if(ours && tick.action==walker::Action::Begin && playback.active()) {
        if(!Gates().valid() || !(mode==Mode::Follow?BeginFollow():BeginCamera())) Stop("camera start refused",true);
    } else if(ours && !playback.active() && manager) {
        Stop(mode==Mode::Follow?last_result:"camera/input/framing gate changed",true);
    }
    if(trace_frame&&ours&&HeroNativeRoute()&&playback.active()&&Gates().valid()){
        CaptureMotionPoint(motion,true);
        if(applied_frames>frames_before){motion[2]=static_cast<unsigned>(motion[2])|16u;for(unsigned n=0;n<3;++n)motion[21+n]=hero_current.root[n];}
        motion[24]=static_cast<double>(applied_frames);motion[25]=static_cast<double>(hero_rig.recenters());motion[26]=hero_rig.entry_elapsed();
        hero_motion_trace.append(motion,true);
    }
}
bool PinModule(HMODULE module,const char* expected) {
    char path[32768]{};
    return module && GetModuleFileNameA(module,path,sizeof(path)) && CitadelCastHashFile(path)==expected;
}
bool BindClient() {
    auto c=GetModuleHandleW(L"client.dll"),e=GetModuleHandleW(L"engine2.dll"),n=GetModuleHandleW(L"networksystem.dll");
    binding_failure="checking";binding_slot=0;
    if(!PinModule(c,kClientHash)) return BindingFailure("client module missing unreadable or hash differs");
    if(!PinModule(e,kEngineHash)) return BindingFailure("engine module missing unreadable or hash differs");
    if(!PinModule(n,kNetworkHash)) return BindingFailure("network module missing unreadable or hash differs");
    client=reinterpret_cast<std::uintptr_t>(c);engine=reinterpret_cast<std::uintptr_t>(e);network=reinterpret_cast<std::uintptr_t>(n);
    if(!aspect) {
        const auto a=g_pCVar->FindConVar("r_aspectratio",true),s=g_pCVar->FindConVar("sv_cheats",true);
        if(!a.IsValidRef()) return BindingFailure("aspect cvar lookup unavailable");
        if(!s.IsValidRef()) return BindingFailure("cheats cvar lookup unavailable");
        ConVarRefAbstract ar(a),sr(s);
        if(!ar.IsConVarDataAvailable()) return BindingFailure("aspect cvar data unavailable");
        if(!sr.IsConVarDataAvailable()) return BindingFailure("cheats cvar data unavailable");
        aspect_type=static_cast<int>(ar.GetType());cheats_type=static_cast<int>(sr.GetType());aspect_flags=ar.GetFlags();
        if(ar.GetType()!=EConVarType_Float32) return BindingFailure("aspect cvar type differs");
        if(sr.GetType()!=EConVarType_Bool) return BindingFailure("cheats cvar type differs");
        if(ar.IsFlagSet(FCVAR_CHEAT|FCVAR_REPLICATED|FCVAR_GAMEDLL)) return BindingFailure("aspect cvar has disallowed flags");
        aspect=std::make_unique<CConVarRef<float>>(ar);cheats=std::make_unique<CConVarRef<bool>>(sr);
    }
    return RuntimeBindings();
}
bool InstallHooks() {
    auto mt=reinterpret_cast<void**>(client+kManagerTable),dt=reinterpret_cast<void**>(client+kDataTable);
    original_manager_frame=reinterpret_cast<Method>(client+0x5d9b90);
    original_data_frame=reinterpret_cast<Method>(client+0x1aaa620);
    original_deactivate=reinterpret_cast<Method>(client+0x5d0d40);
    original_manager_destroy=reinterpret_cast<Destroy>(client+0x5b8a50);
    original_data_destroy=reinterpret_cast<Destroy>(client+0x1aa6d40);
    original_manager_keep=reinterpret_cast<Keep>(client+0x1947440);
    original_observer_destroy=reinterpret_cast<Destroy>(client+0x5eaa00);
    auto observer=reinterpret_cast<void**>(client+kObserverTable);
    original_follow_frame.store(reinterpret_cast<Method>(client+0x614db0));
    original_follow_position.store(reinterpret_cast<Getter>(client+0x5fe830));
    original_follow_angles.store(reinterpret_cast<Getter>(client+0x5fc900));
    const std::array<void**,10> cells={mt+2,dt+3,dt+7,mt,dt,mt+16,observer,observer+3,observer+12,observer+15};
    const std::array<void*,10> before={reinterpret_cast<void*>(original_manager_frame),reinterpret_cast<void*>(original_data_frame),
        reinterpret_cast<void*>(original_deactivate),reinterpret_cast<void*>(original_manager_destroy),reinterpret_cast<void*>(original_data_destroy),
        reinterpret_cast<void*>(original_manager_keep),reinterpret_cast<void*>(original_observer_destroy),
        reinterpret_cast<void*>(original_follow_frame.load()),reinterpret_cast<void*>(original_follow_position.load()),reinterpret_cast<void*>(original_follow_angles.load())};
    const std::array<void*,10> after={reinterpret_cast<void*>(&ManagerFrame),reinterpret_cast<void*>(&DataFrame),
        reinterpret_cast<void*>(&Deactivate),reinterpret_cast<void*>(&ManagerDestroy),reinterpret_cast<void*>(&DataDestroy),
        reinterpret_cast<void*>(&KeepCamera),reinterpret_cast<void*>(&ObserverDestroy),
        reinterpret_cast<void*>(&FollowFrame),reinterpret_cast<void*>(&FollowPosition),reinterpret_cast<void*>(&FollowAngles)};
    for(unsigned n=0;n<hooks.size();++n) if(!hooks[n].install(cells[n],before[n],after[n])) {
        for(auto it=hooks.rbegin();it!=hooks.rend();++it) if(!it->restore())
            Plat_FatalError("CitadelCast could not restore its camera callback pointers.");
        return false;
    }
    return true;
}
bool Carrier(std::string& relative,const walker::Shot& shot=*selected_shot) {
    HMODULE self{}; char path[32768]{};
    if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCSTR>(&RegisterWalkerCommands),&self) || !GetModuleFileNameA(self,path,sizeof(path))) return false;
    namespace fs=std::filesystem;
    const fs::path root=fs::path(path).parent_path().parent_path().parent_path();
    const std::string name=root.filename().string(),prefix="citadelcast_walker_";
    if(name.size()!=prefix.size()+16 || name.compare(0,prefix.size(),prefix)!=0 ||
        name.find_first_not_of("0123456789abcdef",prefix.size())!=std::string::npos) return false;
    std::error_code ec;
    if(!fs::equivalent(root.parent_path(),fs::path(Plat_GetGameDirectory())/"citadel",ec) || ec) return false;
    const auto carrier=root/shot.carrier;
    if(CitadelCastHashFile(carrier.string().c_str())!=shot.hash) return false;
    relative=name+"/"+shot.carrier;return true;
}
bool BeginHeroCamera(){
    // Keep the original selected observer as the read-only target authority and
    // lease return object. Publish one owned native camera pose for all readers.
    follow_owner_thread.store(0,std::memory_order_release);follow_camera=nullptr;follow_permit.invalidate();
    follow::Pose entry{};hero::Target target;
    if(!Gates().valid() || !ObserverSelectionReady(manager) || !ReadNativeFollowPose(initial_camera,entry) ||
       !ReadHeroTarget(initial_camera,target) || !target.same_identity(hero_initial))return false;
    hero_entry_fov=VFunc<float(*)(void*)>(initial_camera,17)(initial_camera);
    const double now=Now();
    if(!std::isfinite(hero_entry_fov) || hero_entry_fov<=1 || hero_entry_fov>=179 ||
       !hero_rig.begin(now,target.root,entry,hero_heading,target.world_angles[1]))return false;
    hero_start_yaw=target.world_angles[1];
    hero_current=target;hero_native=entry;
    return BeginCamera();
}
bool BeginCamera() {
    std::string filename;
    if(!Carrier(filename) || !ManagerValid() || Field<void*>(manager,0x28)!=initial_camera ||
        !observer_lease.active() || observer_lease.camera()!=Key(initial_camera) ||
        !ObserverSelectionReady(manager)) return false;
    const int type=*reinterpret_cast<int*>(client+kDataCameraType);
    if(type<0 || type>65535) return false;
    void* camera=reinterpret_cast<void*(*)(int,void*)>(client+kCameraFactory)(type,manager);
    if(!camera) return false;
    if(Field<std::uintptr_t>(camera,0)!=client+kDataTable) {
        // Factory returned a different type: use its normal deleting destructor,
        // without reading or writing the expected derived layout.
        VFunc<Destroy>(camera,0)(camera,1);return false;
    }
    const auto setup=reinterpret_cast<bool(*)(void*)>(client+kDataSetup);
    const bool loaded=setup(camera) && reinterpret_cast<bool(*)(void*,const char*)>(client+kDataLoad)
        (Field<void*>(camera,0xe0),filename.c_str());
    if(!loaded || !setup(camera) || (HeroNativeRoute() && !Gates().valid()) || !playback.begin_ready(Now())) { VFunc<Destroy>(camera,0)(camera,1);return false; }
    owned_camera=camera;Field<unsigned char>(camera,0x88)=1;
    if(HeroNativeRoute() && !WriteHeroOwnedPose(camera,true)){
        owned_camera=nullptr;VFunc<Destroy>(camera,0)(camera,1);return false;
    }
    VFunc<void(*)(void*,void*)>(manager,10)(manager,camera);
    if(!playback.active() || owned_camera!=camera)return false;
    last_result="playing";Status();
    if(HeroNativeRoute())Msg("CitadelCast Hero started: owned native camera,1-second entry transition within12seconds,entry lens retained.\n");
    else Msg("CitadelCast Shot started: %s, %.6f seconds, bank and framing included.\n",selected_shot->name,selected_shot->duration);
    return playback.active() && owned_camera==camera;
}
void Start(const CCommandContext&,const CCommand& args) {
    std::lock_guard lock(mutex);
    if(take_archive.pending()){Status();Msg("CitadelCast: previous take save pending; retry status before another take.\n");return;}
    const bool library=std::strcmp(args[0],"citadelcast_shot_start")==0;
    if(args.ArgC()!=(library?5:4) || std::strcmp(args[1],"watch") || std::strcmp(args[2],"freecam") || std::strcmp(args[3],"offair")) {
        Msg("Usage: %s watch freecam offair%s (roaming Watch only;3-second countdown).\n",library?"citadelcast_shot_start":"citadelcast_walker_start",library?" <shot-id>":"");return;
    }
    if(shutting_down || playback.active() || observer_lease.active() || observer_lease.blocked() || owned_camera || aspect_written || aspect_inflight || !CommandLine()->HasParm("-dev") || !CommandLine()->HasParm("-insecure") || !BindClient()) {
        Msg("CitadelCast refused: active take, missing flags or unreviewed client/engine/registry.\n");return;
    }
    const auto* requested=library?walker::FindShot(args[4]):&walker::kShots[0];
    if(!requested) { Msg("CitadelCast refused: unknown shot id; use citadelcast_shot_list.\n");return; }
    std::string carrier;
    if(!Carrier(carrier,*requested)) { Msg("CitadelCast refused: missing or changed owned camera data.\n");return; }
    manager=reinterpret_cast<void*(*)(int)>(client+kGetManager)(-1);
    owner_thread=GetCurrentThreadId();
    if(!ManagerValid()) { manager=nullptr;Msg("CitadelCast refused: no reviewed camera manager.\n");return; }
    if(!ObserverSelectionReady(manager)) {
        manager=nullptr;Msg("CitadelCast refused: expected reviewed observer camera with no transition.\n");return;
    }
    initial_camera=Field<void*>(manager,0x28);initial_default=Field<void*>(manager,0x20);
    if(!observer_lease.arm(Key(manager),Key(initial_camera),Key(initial_default)) || !Gates().valid() || !InstallHooks()) {
        Stop("observer camera arming refused",false);
        Msg("CitadelCast refused: reviewed roaming Watch, foreground game, released controls and viewer cheats false required.\n");return;
    }
    selected_shot=requested;
    mode=Mode::Path;
    follow_style=FollowStyle::Native;
    follow_filter={};follow_permit.invalidate();follow_position_copies=follow_angle_copies=0;follow_peak_lag=0;
    observer_return="not cut";
    native_sample={};camera_exit={};
    original_aspect=aspect->Get();aspect_written=false;applied_frames=0;last_elapsed=0;
    if(!std::isfinite(original_aspect) || !playback.arm(Now(),Gates(),selected_shot->duration)) { Stop("arming refused",false);return; }
    watch_attested=true;
    last_result="countdown";Status();
    Msg("CitadelCast Walker: off-air countdown3 seconds. Close console; movement/mouse/Escape or focus loss cancels.\n");
}
void StopCommand(const CCommandContext&,const CCommand&) { std::lock_guard lock(mutex);Stop("operator stop",true); }
void FollowStartCommand(const CCommand& args,bool hero_shot) {
    const double command_began=Now();
    std::lock_guard lock(mutex);
    if((args.ArgC()!=4 && !(hero_shot&&args.ArgC()==5)) || std::strcmp(args[1],"watch") || std::strcmp(args[2],"chase") || std::strcmp(args[3],"offair")){
        Msg("Usage: %s watch chase offair; native hero chase must already be selected.3-second countdown,12-second test.\n",hero_shot?"citadelcast_hero_start":"citadelcast_follow_start");return;
    }
    hero::HeadingPolicy policy=hero::HeadingPolicy::NativeStart;
    if(args.ArgC()==5){
        if(!std::strcmp(args[4],"turn-with-hero"))policy=hero::HeadingPolicy::HeroFollow;
        else if(!std::strcmp(args[4],"hold-bearing"))policy=hero::HeadingPolicy::HeroStart;
        else{Msg("Hero profile must be turn-with-hero or hold-bearing.\n");return;}
    }
    if(take_archive.pending()){Status();Msg("CitadelCast: previous take save pending; retry status before another take.\n");return;}
    if(shutting_down || playback.active() || observer_lease.active() || observer_lease.blocked() || owned_camera || aspect_written || aspect_inflight ||
       !CommandLine()->HasParm("-dev") || !CommandLine()->HasParm("-insecure") || !BindClient()){
        Msg("CitadelCast Follow refused: busy,missing flags or unreviewed client.\n");return;
    }
    if(hero_shot){
        std::string scaffold;
        if(!Carrier(scaffold,walker::kShots[0])){Msg("CitadelCast Hero refused: unchanged owned camera scaffold required.\n");return;}
        selected_shot=&walker::kShots[0];
    }
    manager=reinterpret_cast<void*(*)(int)>(client+kGetManager)(-1);owner_thread=GetCurrentThreadId();
    if(!ObserverSelectionReady(manager)){manager=nullptr;Msg("CitadelCast Follow refused: reviewed native observer/no transition required.\n");return;}
    initial_camera=Field<void*>(manager,0x28);initial_default=Field<void*>(manager,0x20);
    if(hero_shot && (!ViewerReady() || !ReadHeroTarget(initial_camera,hero_initial,policy!=hero::HeadingPolicy::NativeStart))){
        manager=initial_camera=initial_default=nullptr;Msg("CitadelCast Hero refused: %s. Use the read-only citadelcast_hero_probe first.\n",hero_target_reason);return;
    }
    if(!observer_lease.arm(Key(manager),Key(initial_camera),Key(initial_default)) || !Gates().valid() || !InstallHooks()){
        Stop("follow arming refused",false);return;
    }
    mode=Mode::Follow;follow_style=hero_shot?FollowStyle::Hero:FollowStyle::Native;
    hero_heading=policy;hero_start_yaw=0;
    hero_cost={};hero_reads={};hero_camera_reads={};failed_gate_mask=0;hero_entry_fov=0;hero_primed=false;hero_field_updates=0;
    follow_filter={};hero_rig={};hero_current=hero_initial;hero_native={};follow_permit.invalidate();follow_camera=nullptr;
    follow_position_copies=follow_angle_copies=0;follow_peak_lag=0;
    follow_manager_frames=follow_native_frames=follow_gate_checks=0;
    follow_last_manager=follow_max_manager_gap=follow_max_gate_ms=0;
    follow_owner_thread.store(0,std::memory_order_release);
    native_sample={};camera_exit={};applied_frames=0;last_elapsed=0;observer_return="native chase retained";
    if(!playback.arm(Now(),Gates(),12)){Stop("follow clock arming refused",false);return;}
    if(hero_shot&&!take_archive.arm()){Stop("take archive arming refused",false);return;}
    hero_motion_trace.reset(Now());hero_motion_read_cost={};
    hero_fresh_target.reset();hero_native_source_cost={};
    const double command_ended=Now();hero_arming_wall_ms=std::isfinite(command_began)&&std::isfinite(command_ended)&&command_ended>=command_began?1000*(command_ended-command_began):0;
    watch_attested=true;last_result="countdown";Status();
    Msg("CitadelCast Follow: native chase is operator-attested. Off-air countdown3 seconds. Release controls;movement keys,mouse buttons,Escape/focus loss cancel.\n");
    if(hero_shot)Msg("CitadelCast Hero take %llu: %s.\n",static_cast<unsigned long long>(take_archive.id()),hero::Profile(hero_heading));
}
void FollowStart(const CCommandContext&,const CCommand& args){FollowStartCommand(args,false);}
void HeroStart(const CCommandContext&,const CCommand& args){FollowStartCommand(args,true);}
void HeroProbe(const CCommandContext&,const CCommand& args){
    std::lock_guard lock(mutex);
    if(args.ArgC()!=1 || take_archive.pending() || playback.active() || observer_lease.active() ||
       !CommandLine()->HasParm("-dev") || !CommandLine()->HasParm("-insecure") || !BindClient() || !ViewerReady()){
        Msg("CitadelCast Hero probe refused: idle reviewed dev/insecure Watch viewer with cheatsfalse required.\n");return;
    }
    void* current=reinterpret_cast<void*(*)(int)>(client+kGetManager)(-1);
    if(!ObserverSelectionReady(current)){Msg("CitadelCast Hero probe: reviewed observer camera with no transition required.\n");return;}
    hero::TargetReader reader(client,citadelcast_memory::CheckedRead{},true);hero::Target target;
    const bool ready=reader.sample(reinterpret_cast<std::uintptr_t>(Field<void*>(current,0x28)),target);
    Msg("CitadelCast Hero probe: %s; observer mode%d; validated handle%u; root %.3f %.3f %.3f. No camera or settings changed.\n",reader.reason(),reader.observed_mode(),target.handle,target.root[0],target.root[1],target.root[2]);
    Msg("Hero world rotation: present=%s; pitch %.3f yaw %.3f roll %.3f.\n",target.facing_present?"yes":"no",target.world_angles[0],target.world_angles[1],target.world_angles[2]);
    const auto& diagnostic=reader.diagnostic();
    Msg("Hero target diagnostic: sample%u; selected handle read=%s value%u; camera handle read=%s value%u; last handle resolution=%s. Partial readbacks do not authorize a take.\n",diagnostic.sample,diagnostic.selected_handle_read?"yes":"no",diagnostic.selected_handle,diagnostic.camera_handle_read?"yes":"no",diagnostic.camera_handle,diagnostic.resolution);
    Msg("Hero scene diagnostic: table read=%s; in reviewed client=%s; table RVA0x%x; type=%s. No camera or settings changed.\n",diagnostic.scene_table_read?"yes":"no",diagnostic.scene_table_in_client?"yes":"no",diagnostic.scene_table_rva,diagnostic.scene_type);
    hero_probe_present=true;hero_probe_ready=ready;hero_probe_mode=reader.observed_mode();hero_probe_target=target;hero_probe_reason=reader.reason();hero_probe_diagnostic=diagnostic;
    Status();
}
void ListShots(const CCommandContext&,const CCommand&) {
    std::lock_guard lock(mutex);
    for(const auto& shot:walker::kShots) Msg("CitadelCast shot: %s | %s | %.6f seconds.\n",shot.id,shot.name,shot.duration);
}
void StatusCommand(const CCommandContext&,const CCommand&) {
    std::lock_guard lock(mutex);
    const bool reviewed=BindClient();
    const bool broadcast=reviewed && ViewerReady();
    bool observer_selected=false;
    if(broadcast) {
        void* current_manager=reinterpret_cast<void*(*)(int)>(client+kGetManager)(-1);
        if(current_manager && Field<std::uintptr_t>(current_manager,0)==client+kManagerTable)
            observer_selected=ObserverSelectionReady(current_manager);
    }
    const char* phases[]={"idle","countdown","playing","endpoint"};
    Msg("Hero comparison: take %llu, profile %s, final record pending=%s.\n",static_cast<unsigned long long>(take_archive.id()),hero::Profile(hero_heading),take_archive.pending()?"yes":"no");
    Msg("CitadelCast Shot: %s, %s, %s, frames%llu, time%.6f/%.6f.\n",
        ShotId(),phases[static_cast<unsigned>(playback.phase())],last_result,applied_frames,last_elapsed,playback.duration());
    if(mode==Mode::Follow)Msg("Follow: position copies%llu,angle copies%llu,peak lag%.3f units; native chase is operator-attested.\n",follow_position_copies,follow_angle_copies,follow_peak_lag);
    Msg("Readiness: reviewed build/interfaces=%s, BROADCAST and viewer cheats=false=%s, observer camera eligible=%s, foreground=%s, controls released=%s, framing restore pending=%s.\n",
        reviewed?"yes":"no",broadcast?"yes":"no",observer_selected?"yes":"no",Foreground()?"yes":"no",InputIdle()?"yes":"no",aspect_written?"yes":"no");
    Msg("Readiness detail: %s; slot=%u; aspect type=%d; cheats type=%d; aspect flags=0x%llx.\n",
        binding_failure,binding_slot,aspect_type,cheats_type,aspect_flags);
    const auto camera=ObserveCamera();
    Msg("Camera diagnostic: manager=%s, reviewed=%s, slot0 same=%s; active=%s; retained=%s; active equals retained=%s; transition=%s.\n",
        camera.manager_type,camera.manager_reviewed?"yes":"no",camera.slot0_same?"yes":"no",camera.active_type,camera.retained_type,camera.active_default?"yes":"no",camera.transition_present?"yes":"no");
    Status(&camera);
}
} // namespace

bool RegisterWalkerCommands() {
    std::lock_guard lock(mutex);
    if(registered || !g_pCVar) return false;
    const char* names[]={"citadelcast_walker_start","citadelcast_walker_stop","citadelcast_walker_status","citadelcast_shot_list","citadelcast_shot_start","citadelcast_follow_start","citadelcast_follow_stop","citadelcast_follow_status","citadelcast_hero_probe","citadelcast_hero_start","citadelcast_hero_stop","citadelcast_hero_status"};
    const char* help[]={"Start the original Walker shot: watch freecam offair;3-second countdown.","Stop shot and restore owned framing/original observer camera.","Read shot adapter state; no camera or setting changes.","List the four compiled shots; no camera or setting changes.","Start a compiled shot: watch freecam offair <shot-id>;3-second countdown.","Filter the native chase view: watch chase offair;3-second countdown,12-second test.","Disable follow filter immediately; leave native chase selected.","Read adapter/follow status; no camera or setting changes.","Read selected hero identity and world origin; no camera or setting changes.","Three-quarter hero shot: watch chase offair [turn-with-hero|hold-bearing];3-second countdown,12seconds; omitted profile keeps legacy framing.","Stop hero shot immediately; preserve native chase.","Read hero shot state; no camera or setting changes."};
    FnCommandCallback_t callbacks[]={Start,StopCommand,StatusCommand,ListShots,Start,FollowStart,StopCommand,StatusCommand,HeroProbe,HeroStart,StopCommand,StatusCommand};
    static_assert(std::size(names)==std::size(help) && std::size(names)==std::size(callbacks));
    static_assert(std::size(names)==std::tuple_size_v<decltype(commands)>);
    for(const char* name:names) if(g_pCVar->FindConCommand(name,true).IsValidRef()) return false;
    for(unsigned n=0;n<commands.size();++n) {
        ConCommandCreation_t setup{};setup.m_pszName=names[n];setup.m_pszHelpString=help[n];
        setup.m_nFlags=FCVAR_RELEASE|FCVAR_CLIENTDLL;setup.m_CBInfo=ConCommandCallbackInfo_t(callbacks[n]);
        commands[n]=g_pCVar->RegisterConCommand(setup,0);
        if(!commands[n].IsValidRef()) {
            for(auto& command:commands) if(command.IsValidRef()) { g_pCVar->UnregisterConCommandCallbacks(command);command.InvalidateRef(); }
            return false;
        }
    }
    registered=true;return true;
}
void ShutdownWalker() {
    std::lock_guard lock(mutex);
    shutting_down=true;Stop("shutdown",true);
    for(auto it=hooks.rbegin();it!=hooks.rend();++it) if(!it->restore())
        Plat_FatalError("CitadelCast could not restore its owned camera callbacks.");
    for(auto& command:commands) if(command.IsValidRef()) { if(g_pCVar)g_pCVar->UnregisterConCommandCallbacks(command);command.InvalidateRef(); }
    registered=false;aspect.reset();cheats.reset();
}
