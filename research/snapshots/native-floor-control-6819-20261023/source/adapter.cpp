// Bounded native line/sphere wall measurement. No camera creation, selection,
// pose/lens/cvar writes or game command execution. Native callbacks forward.
#include "adapter.hpp"
#include "wall_native.hpp"
#include "wall_schedule.hpp"
#include "floor_control.hpp"
#include "pins.hpp"
#include "owned_slot.hpp"
#include "checked_page_read.hpp"
#include "hero_target.hpp"
#include "icvar.h"
#include "icommandline.h"
#include "tier0/platform.h"
#include <windows.h>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>

extern std::string CitadelCastHashFile(const char*);
namespace {
constexpr std::uintptr_t kWorldHolderCell=0x3428650,kWorldHolder=0x3e33330;
constexpr std::uintptr_t kNativeGlobalsCell=0x34331c0,kMainThreadFunction=0x173b80;
using Method=void(*)(void*);
using Trace=bool(*)(void*,const void*,const float*,const float*,void*,void*);
using Getter=float*(*)(void*,float*);
constexpr std::uintptr_t kTraceShape=0x17e4fe0,kFilterTable=0x26351b0;
using MainThread=bool(*)();
std::uintptr_t client=0,engine=0,network=0,tier=0;
std::atomic<Method> native_manager{},native_observer{};
std::atomic<DWORD> owner{0};
MainThread main_thread=nullptr;
std::recursive_mutex mutex;
std::array<OwnedSlot,2> hooks;
std::array<ConCommandRef,3> commands;
std::unique_ptr<CConVarRef<bool>> cheats,director;
wall_query::Schedule session;
void* selected_manager=nullptr;void* selected_camera=nullptr;
hero::Target initial_target;
struct QueryRecord {
    bool called=false,guard_ok=false,native_hit=false;double milliseconds=0;
    float fraction=0;std::uint8_t tag=0,inside=0,exact=0;
    std::array<float,3> returned_start{},returned_end{};
};
struct Record {
    bool attempted=false,core_valid=false,accepted=false,world_checks=false,floor_contacts=false;
    unsigned scene=0,calls=0,context_snapshots=0,observer_updates=0;std::uint32_t handle=0;
    double elapsed=0,total_ms=0;float curtime_before=0,curtime_after=0;
    std::array<float,3> root{},eye{};std::array<collision_contract::Request,2> requests{};
    std::array<QueryRecord,2> query{};const char* reason="not sampled";
};
std::array<Record,3> records;bool clear_passed=false;
std::uint64_t frame_serial=0;std::uintptr_t batch_world=0;
thread_local bool in_query=false;
bool registered=false,shutting_down=false;
const char* binding_reason="not checked";
thread_local bool in_manager=false,observing=false;
thread_local unsigned observer_updates=0;

double Now(){LARGE_INTEGER t{},f{};return QueryPerformanceCounter(&t)&&QueryPerformanceFrequency(&f)&&f.QuadPart>0?
    static_cast<double>(t.QuadPart)/f.QuadPart:NAN;}
template<class T>bool Read(std::uintptr_t at,T& value){citadelcast_memory::CheckedRead read;return read(at,&value,sizeof(value));}
bool Table(void* object,std::uintptr_t rva){std::uintptr_t table{};return object&&Read(reinterpret_cast<std::uintptr_t>(object),table)&&table==client+rva;}
bool Modules(){return client&&engine&&network&&tier&&
    reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"client.dll"))==client&&
    reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"engine2.dll"))==engine&&
    reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"networksystem.dll"))==network&&
    reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"tier0.dll"))==tier;}
bool Pin(HMODULE module,const char* sha){char path[32768]{};return module&&GetModuleFileNameA(module,path,sizeof(path))&&CitadelCastHashFile(path)==sha;}
bool Slot(std::uintptr_t table,unsigned slot,std::uintptr_t expected){
    auto cell=reinterpret_cast<void**>(client+table)+slot;void* value{};
    if(!Read(reinterpret_cast<std::uintptr_t>(cell),value))return false;
    for(const auto& hook:hooks)if(hook.installed&&hook.cell==cell&&value==hook.after)return true;
    return reinterpret_cast<std::uintptr_t>(value)==client+expected;
}
bool TraceBindings(){
    constexpr std::array<unsigned char,10> entry={0x48,0x89,0x54,0x24,0x10,0x48,0x89,0x4c,0x24,0x08};
    std::array<unsigned char,10> actual{};std::uintptr_t destructor{},callback{};
    return Read(client+kTraceShape,actual)&&actual==entry&&Read(client+kFilterTable,destructor)&&
        destructor==client+0x24aba0&&Read(client+kFilterTable+8,callback)&&callback==client+0x2a23f0;
}
bool Bindings(){
    if(!Modules()||!main_thread||reinterpret_cast<std::uintptr_t>(main_thread)!=tier+kMainThreadFunction)return false;
    for(const auto& p:kManagerSlotPins)if(!Slot(kManagerTable,p.slot,p.method))return false;
    for(const auto& p:kObserverSlotPins)if(!Slot(kObserverTable,p.slot,p.method))return false;
    std::uintptr_t connected{};
    return Read(engine+0x4e2790+39*8,connected)&&connected==engine+kFullyConnected&&TraceBindings();
}
bool Bind(){
    if(shutting_down)return false;
    const auto c=GetModuleHandleW(L"client.dll"),e=GetModuleHandleW(L"engine2.dll"),
        n=GetModuleHandleW(L"networksystem.dll"),t=GetModuleHandleW(L"tier0.dll");
    binding_reason="unreviewed or unavailable module";
    if(!Pin(c,kClientHash)||!Pin(e,kEngineHash)||!Pin(n,kNetworkHash)||!Pin(t,kTierHash))return false;
    client=reinterpret_cast<std::uintptr_t>(c);engine=reinterpret_cast<std::uintptr_t>(e);
    network=reinterpret_cast<std::uintptr_t>(n);tier=reinterpret_cast<std::uintptr_t>(t);
    main_thread=reinterpret_cast<MainThread>(GetProcAddress(t,"ThreadInMainThread"));
    binding_reason="native main-thread export differs";
    if(reinterpret_cast<std::uintptr_t>(main_thread)!=tier+kMainThreadFunction)return false;
    if(!cheats||!director){
        binding_reason="required bool cvar unavailable";
        const auto a=g_pCVar->FindConVar("sv_cheats",true),b=g_pCVar->FindConVar("spec_autodirector",true);
        if(!a.IsValidRef()||!b.IsValidRef())return false;
        ConVarRefAbstract ar(a),br(b);
        if(!ar.IsConVarDataAvailable()||!br.IsConVarDataAvailable()||ar.GetType()!=EConVarType_Bool||br.GetType()!=EConVarType_Bool)return false;
        cheats=std::make_unique<CConVarRef<bool>>(ar);director=std::make_unique<CConVarRef<bool>>(br);
    }
    binding_reason="camera or connection slots differ";
    if(!Bindings())return false;
    binding_reason="ready";return true;
}
bool Viewer(){
    if(!Modules()||!cheats||!director||cheats->Get()||director->Get()||
       !reinterpret_cast<bool(*)()>(engine+kFullyConnected)())return false;
    std::uintptr_t game_client{},channel{},table{},method{};
    if(!Read(engine+kNetworkClientGlobal,game_client)||!game_client||!Read(game_client+0xf0,channel)||!channel||
       !Read(channel,table)||table!=network+kChannelTable||!Read(table+8,method)||method!=network+kChannelStatusLabel)return false;
    const char* label=reinterpret_cast<const char*(*)(void*)>(method)(reinterpret_cast<void*>(channel));
    std::array<char,10> text{};return label&&Read(reinterpret_cast<std::uintptr_t>(label),text)&&std::strncmp(text.data(),"BROADCAST",10)==0;
}
bool FocusInput(){
    DWORD pid{};const auto w=GetForegroundWindow();
    if(!w||!GetWindowThreadProcessId(w,&pid)||pid!=GetCurrentProcessId())return false;
    constexpr int keys[]={'W','A','S','D',VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,VK_SHIFT,VK_CONTROL,VK_ESCAPE,VK_LBUTTON,VK_RBUTTON};
    for(int key:keys)if(GetAsyncKeyState(key)&0x8000)return false;
    return true;
}
void* CurrentManager(){return reinterpret_cast<void*(*)(int)>(client+kGetManager)(-1);}
bool Selection(void* manager,void*& camera){
    if(!Table(manager,kManagerTable))return false;
    const auto address=reinterpret_cast<std::uintptr_t>(manager);
    void* retained{};void* previous{};unsigned char transition{};
    return Read(address+0x28,camera)&&Read(address+0x20,retained)&&Read(address+0x30,previous)&&
        Read(address+0x38,transition)&&!previous&&!transition&&camera!=retained&&
        Table(camera,kObserverTable)&&Table(retained,kRetainedTable);
}
bool Gates(){
    if(shutting_down||owner.load(std::memory_order_acquire)!=GetCurrentThreadId()||!Bindings()||!main_thread()||!Viewer()||!FocusInput())return false;
    void* camera{};std::uint32_t handle{};
    return CurrentManager()==selected_manager&&Selection(selected_manager,camera)&&camera==selected_camera&&
        Read(reinterpret_cast<std::uintptr_t>(camera)+0xb0,handle)&&handle==initial_target.handle;
}
bool World(std::uintptr_t& world){
    std::uintptr_t holder{};return Read(client+kWorldHolderCell,holder)&&holder==client+kWorldHolder&&Read(holder,world)&&world;
}
struct Snapshot {
    bool valid=false;std::uintptr_t world=0,globals=0;float curtime=0;
    hero::Target target;std::array<float,3> eye{};
};
Snapshot Capture(){
    Snapshot s;if(!Gates())return s;unsigned char simulation{};
    if(!World(s.world)||!Read(client+kNativeGlobalsCell,s.globals)||!s.globals||
       !Read(s.globals+0x30,s.curtime)||!std::isfinite(s.curtime)||s.curtime<=0||
       !Read(s.globals+0x40,simulation)||simulation)return s;
    hero::TargetReader reader(client,citadelcast_memory::CheckedRead{});
    if(!reader.sample(reinterpret_cast<std::uintptr_t>(selected_camera),s.target)||!s.target.same_identity(initial_target))return s;
    // Pinned leaf getter copies the native rendered-eye field+0x120 to caller
    // storage; it writes no camera field and returns exactly that storage.
    if(reinterpret_cast<Getter>(client+0x5fe830)(selected_camera,s.eye.data())!=s.eye.data())return s;
    for(float n:s.eye)if(!std::isfinite(n))return s;
    s.valid=Gates();return s;
}
void ExecuteBatch(){
    Record& record=records[session.count()-1];
    if(record.attempted||in_query){record.reason="reentrant/repeated query refused";return;}
    record.attempted=true;in_query=true;
    struct Reset{~Reset(){in_query=false;}}reset;
    const double began=Now();wall_query::Budget budget(began);Snapshot seed=Capture();
    if(!seed.valid){record.reason="initial query snapshot refused";return;}
    batch_world=seed.world;record.curtime_before=seed.curtime;record.handle=seed.target.handle;record.eye=seed.eye;
    for(unsigned i=0;i<3;++i)record.root[i]=static_cast<float>(seed.target.root[i]);
    const bool segment=record.scene==3?floor_control::Requests(record.root,record.requests):
        wall_query::Requests(record.root,record.eye,record.requests);
    if(!segment){record.reason="camera/hero/floor segment invalid";return;}
    bool fault=false,contexts_good=true;const char* fault_reason="context/result validation failed";
    auto observe=[&]{
        const auto s=Capture();++record.context_snapshots;record.curtime_after=s.curtime;
        const double time=Now();const bool budget_ok=budget.allowed(time);
        contexts_good=contexts_good&&s.valid&&s.world==batch_world&&s.globals==seed.globals&&s.target.same_identity(seed.target);
        collision_contract::Context c;
        c.world=s.world;c.target=s.target.handle;c.camera=reinterpret_cast<std::uintptr_t>(selected_camera);
        c.thread=GetCurrentThreadId();c.frame=frame_serial;
        c.reviewed=s.valid&&contexts_good&&!fault&&budget_ok&&TraceBindings();
        c.native_phase=in_manager&&observing&&in_query&&observer_updates==1;
        c.owner_thread=owner.load(std::memory_order_acquire)==GetCurrentThreadId()&&main_thread();
        c.watch=c.cheats_false=c.native_chase=c.foreground=c.controls_released=s.valid;
        if(!budget_ok)fault_reason="query batch read/time budget exceeded";
        return c;
    };
    auto invoke=[&](const collision_contract::Request& request){
        const unsigned index=record.calls;
        if(index>=2){fault=true;fault_reason="query count exceeded";return collision_contract::RawResult{};}
        QueryRecord& q=record.query[index];
        // Pass the ENGINE'S static query interface, never a retained world
        // pointer. TraceShape itself resolves/checks its current world.
        const double start=Now();
        const auto out=wall_query::Invoke(reinterpret_cast<Trace>(client+kTraceShape),
            reinterpret_cast<void*>(client+kWorldHolder),client+kFilterTable,request);
        const double ended=Now();q.milliseconds=1000*(ended-start);q.called=out.called;q.guard_ok=out.guard_ok;q.native_hit=out.result.hit;
        if(out.called)++record.calls;
        if(out.guard_ok){
            const auto bytes=std::span<const std::byte>(out.result.bytes);
            q.returned_start=collision_contract::Read<std::array<float,3>>(bytes,0x78);
            q.returned_end=collision_contract::Read<std::array<float,3>>(bytes,0x84);
            q.fraction=collision_contract::Read<float>(bytes,0xac);
            q.tag=collision_contract::Read<std::uint8_t>(bytes,0xba);
            q.inside=collision_contract::Read<std::uint8_t>(bytes,0xbb);
            q.exact=collision_contract::Read<std::uint8_t>(bytes,0xbc);
        }
        if(!out.called||!out.guard_ok){fault=true;fault_reason="native result extent guard failed";}
        if(!budget.finish_call(start,ended)){fault=true;fault_reason="native query cost/time budget exceeded; further calls refused";}
        return out.result;
    };
    collision_contract::OneSample sample;sample.arm();std::array<collision_contract::Reading,2> readings;
    record.core_valid=sample.run(record.requests,readings,observe,invoke);
    record.floor_contacts=record.scene==3&&record.core_valid&&floor_control::ContactPair(readings);
    record.total_ms=1000*(Now()-began);record.world_checks=contexts_good;
    record.reason=record.core_valid?"native query results validated":
        (!fault&&contexts_good&&budget.allowed(Now())?sample.reason():fault_reason);
}
void NativeObserver(void* camera){
    native_observer.load(std::memory_order_acquire)(camera);
    if(owner.load(std::memory_order_acquire)==GetCurrentThreadId()&&in_manager&&observing&&camera==selected_camera){
        ++observer_updates;
        if(observer_updates==1&&session.active())ExecuteBatch();
        else session.finish(false,"multiple selected observer updates");
    }
}
void NativeManager(void* object){
    const auto native=native_manager.load(std::memory_order_acquire);
    if(owner.load(std::memory_order_acquire)!=GetCurrentThreadId()||object!=selected_manager){native(object);return;}
    std::lock_guard lock(mutex);
    if(in_manager){session.finish(false,"reentrant manager update");native(object);return;}
    const bool was_active=session.active();const double began=Now();
    const bool due=session.due(began,Gates());
    ++frame_serial;observer_updates=0;batch_world=0;in_manager=true;observing=due;
    struct Reset{~Reset(){in_manager=observing=false;}}reset;
    native(object);observing=false;in_manager=false;
    if(due&&session.active()){
        Record& r=records[session.count()-1];std::uintptr_t end_world{};
        r.observer_updates=observer_updates;r.elapsed=session.elapsed(Now());
        const bool end_ok=observer_updates==1&&Gates()&&World(end_world)&&end_world==batch_world;
        r.world_checks=r.world_checks&&end_ok;
        r.accepted=r.attempted&&r.core_valid&&r.calls==2&&end_ok&&std::isfinite(r.total_ms)&&r.total_ms<=10;
        if(!r.attempted)r.reason="selected observer query phase not reached";
        else if(!end_ok)r.reason="post-manager identity/world gate changed";
        else if(r.accepted&&r.scene==0&&(r.query[0].native_hit||r.query[1].native_hit)){
            r.accepted=false;r.reason="clear-space control found contact; stop for review";
        }else if(r.accepted&&r.scene==3&&!r.floor_contacts){
            r.accepted=false;r.reason="floor control did not return two outside-start contacts; stop for review";
        }else if(r.accepted){r.reason="two native queries complete; native chase unchanged";if(r.scene==0)clear_passed=true;}
        session.finish(r.accepted,r.reason);
    }
    if(was_active&&!session.active()&&session.count()){
        Record& r=records[session.count()-1];r.observer_updates=observer_updates;
        if(!r.accepted)r.reason=session.reason();
    }
    batch_world=0;
    if(was_active&&!session.active()){
        owner.store(0,std::memory_order_release);
        Msg("CitadelCast wall sample%u: %s. Run citadelcast_wall_status to save results before another sample.\n",session.count(),session.reason());
    }
}
bool Install(){
    native_manager.store(reinterpret_cast<Method>(client+0x5d9b90),std::memory_order_release);
    native_observer.store(reinterpret_cast<Method>(client+0x614db0),std::memory_order_release);
    const std::array<void**,2> cells={reinterpret_cast<void**>(client+kManagerTable)+2,reinterpret_cast<void**>(client+kObserverTable)+3};
    const std::array<void*,2> before={reinterpret_cast<void*>(native_manager.load()),reinterpret_cast<void*>(native_observer.load())};
    const std::array<void*,2> after={reinterpret_cast<void*>(&NativeManager),reinterpret_cast<void*>(&NativeObserver)};
    for(unsigned i=0;i<2;++i)if(!hooks[i].install(cells[i],before[i],after[i])){
        for(auto it=hooks.rbegin();it!=hooks.rend();++it)if(!it->restore())Plat_FatalError("CitadelCast wall callback restoration failed.");
        return false;
    }return true;
}
void Number(FILE* f,double n){if(std::isfinite(n))std::fprintf(f,"%.9g",n);else std::fputs("null",f);}
void Vec(FILE* f,const std::array<float,3>& v){std::fputs("[",f);for(unsigned i=0;i<3;++i){if(i)std::fputs(",",f);Number(f,v[i]);}std::fputs("]",f);}
const char* Scene(unsigned scene){return scene==0?"clear":scene==1?"wall":scene==2?"corner":"floor";}
bool Save(bool shutdown=false){
    HMODULE self{};char path[32768]{};
    if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCSTR>(&RegisterWalkerCommands),&self)||!GetModuleFileNameA(self,path,sizeof(path)))return false;
    const std::string target=std::string(path)+".walker-status.json",temp=target+".tmp";
    FILE* f{};if(fopen_s(&f,temp.c_str(),"wb"))return false;
    unsigned calls=0;for(const auto& r:records)calls+=r.calls;
    std::fprintf(f,"{\"kind\":\"native_wall_query_diagnostic\",\"pid\":%lu,\"phase\":0,\"result\":\"%s\",\"aspect_restore_pending\":false,\"observer_lease_active\":false,\"observer_cleanup_unverified\":false,\"camera_pose_writes\":0,\"camera_selections\":0,\"physics_query_calls\":%u,\"sample_state\":%u,\"sample_result\":\"%s\",\"sample_count\":%u,\"clear_control_passed\":%s,\"samples\":[",
        GetCurrentProcessId(),shutdown?"shutdown":session.reason(),calls,static_cast<unsigned>(session.state()),session.reason(),session.count(),clear_passed?"true":"false");
    for(unsigned i=0;i<session.count();++i){const auto& r=records[i];if(i)std::fputs(",",f);
        std::fprintf(f,"{\"id\":%u,\"scene\":\"%s\",\"accepted\":%s,\"reason\":\"%s\",\"attempted\":%s,\"core_valid\":%s,\"world_context_checks\":%s,\"observer_updates\":%u,\"selected_handle\":%u,\"calls\":%u,\"context_snapshots\":%u,\"elapsed\":",
            i+1,Scene(r.scene),r.accepted?"true":"false",r.reason,r.attempted?"true":"false",r.core_valid?"true":"false",r.world_checks?"true":"false",r.observer_updates,r.handle,r.calls,r.context_snapshots);
        Number(f,r.elapsed);std::fprintf(f,",\"floor_contacts\":%s,\"query_batch_ms\":",r.floor_contacts?"true":"false");Number(f,r.total_ms);
        std::fputs(",\"native_curtime_before\":",f);Number(f,r.curtime_before);std::fputs(",\"native_curtime_after\":",f);Number(f,r.curtime_after);
        std::fputs(",\"hero_cached_root\":",f);Vec(f,r.root);std::fputs(",\"native_eye\":",f);Vec(f,r.eye);std::fputs(",\"queries\":[",f);
        for(unsigned n=0;n<r.calls;++n){const auto& q=r.query[n];const auto& req=r.requests[n];if(n)std::fputs(",",f);
            std::fprintf(f,"{\"shape\":\"%s\",\"radius\":%.9g,\"guard_ok\":%s,\"native_hit\":%s,\"raw_tag\":%u,\"raw_start_solid\":%u,\"raw_exact_point\":%u,\"query_ms\":",
                n?"sphere":"line",req.radius,q.guard_ok?"true":"false",q.native_hit?"true":"false",unsigned(q.tag),unsigned(q.inside),unsigned(q.exact));
            Number(f,q.milliseconds);std::fputs(",\"fraction\":",f);Number(f,q.fraction);
            std::fputs(",\"requested_start\":",f);Vec(f,req.start);std::fputs(",\"requested_end\":",f);Vec(f,req.end);
            std::fputs(",\"returned_start\":",f);Vec(f,q.returned_start);std::fputs(",\"returned_end\":",f);Vec(f,q.returned_end);std::fputs("}",f);
        }std::fputs("]}",f);
    }
    std::fputs("],\"query_phase\":\"inside_manager_after_selected_native_observer\",\"world_lease_claimed\":false,\"filter_object_set\":1,\"filter_interacts_with\":\"0x20000000001081\",\"filter_excludes\":\"0x14000000202c0000\",\"query_scope\":\"native_camera_contents_static_only_not_visual_visibility\"}\n",f);
    const bool wrote=std::ferror(f)==0,closed=std::fclose(f)==0;
    const bool saved=wrote&&closed&&MoveFileExA(temp.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
    if(saved&&!session.active())session.saved();return saved;
}
void StatusCommand(const CCommandContext&,const CCommand&){
    std::lock_guard lock(mutex);const bool bound=Bind();
    if(session.active()&&session.elapsed(Now())>4){session.finish(false,"sample deadline exceeded");owner.store(0,std::memory_order_release);}
    void* camera{};hero::Target target;bool target_ready=false;
    const bool viewer=bound&&Viewer(),selected=viewer&&Selection(CurrentManager(),camera);
    if(selected){hero::TargetReader reader(client,citadelcast_memory::CheckedRead{});target_ready=reader.sample(reinterpret_cast<std::uintptr_t>(camera),target);}
    const bool saved=Save();unsigned calls=0;for(const auto& r:records)calls+=r.calls;
    Msg("CitadelCast wall query: %s; samples%u/3,queries%u,saved=%s,blocked=%s,clear-control=%s. Camera writes0.\n",session.reason(),session.count(),calls,saved?"yes":"no",session.blocked()?"yes":"no",clear_passed?"yes":"no");
    Msg("Wall readiness: reviewed=%s (%s),Watch/cheatsfalse/directorfalse=%s,selected hero=%s,native main thread=%s,foreground/controls=%s.\n",bound?"yes":"no",binding_reason,viewer?"yes":"no",target_ready?"yes":"no",bound&&main_thread()?"yes":"no",FocusInput()?"yes":"no");
    if(session.count()){const auto& r=records[session.count()-1];for(unsigned i=0;i<r.calls;++i)Msg("Wall sample%u %s: hit=%s,fraction%.6f,start-solid%u,rawtag%u,guard=%s,cost%.3fms.\n",session.count(),i?"sphere8":"line",r.query[i].native_hit?"yes":"no",r.query[i].fraction,unsigned(r.query[i].inside),unsigned(r.query[i].tag),r.query[i].guard_ok?"yes":"no",r.query[i].milliseconds);}
}
void Start(const CCommandContext&,const CCommand& args){
    std::lock_guard lock(mutex);unsigned scene=4;
    if(args.ArgC()==5){if(!std::strcmp(args[4],"clear"))scene=0;else if(!std::strcmp(args[4],"wall"))scene=1;else if(!std::strcmp(args[4],"corner"))scene=2;else if(!std::strcmp(args[4],"floor"))scene=3;}
    if(args.ArgC()!=5||std::strcmp(args[1],"watch")||std::strcmp(args[2],"chase")||std::strcmp(args[3],"offair")||scene==4){
        Msg("Usage: citadelcast_wall_start watch chase offair <clear|wall|corner|floor>;clear control first.3s countdown,two queries,native chase unchanged.\n");return;}
    if(session.active()||session.pending()||session.blocked()||session.count()>=3||(!clear_passed&&scene!=0)){
        Msg("Wall sample refused: busy,unsaved,blocked,limit reached or clear control required. Run wall_status; audit a refusal before any retry.\n");return;}
    if(!CommandLine()->HasParm("-dev")||!CommandLine()->HasParm("-insecure")||!Bind()||!main_thread()||!Viewer()||!FocusInput()){
        Msg("Wall sample refused: focused reviewed main-thread Watch/cheatsfalse/directorfalse/released controls required.\n");return;}
    selected_manager=CurrentManager();
    if(!Selection(selected_manager,selected_camera)){Msg("Wall sample refused: selected native chase/no transition required.\n");return;}
    hero::TargetReader reader(client,citadelcast_memory::CheckedRead{});
    if(!reader.sample(reinterpret_cast<std::uintptr_t>(selected_camera),initial_target)){Msg("Wall sample refused: %s.\n",reader.reason());return;}
    owner.store(GetCurrentThreadId(),std::memory_order_release);
    if(!Gates()||!Install()||!session.arm(Now(),Gates())){owner.store(0,std::memory_order_release);Msg("Wall arming refused; native chase preserved.\n");return;}
    records[session.count()-1]=Record{};records[session.count()-1].scene=scene;
    Save();Msg("CitadelCast wall %s sample%u:3second countdown,two native queries. Close console/release controls; stay focused. Native chase stays unchanged.\n",Scene(scene),session.count());
}
void Stop(const CCommandContext&,const CCommand&){std::lock_guard lock(mutex);session.finish(false,"operator stop");owner.store(0,std::memory_order_release);Save();Msg("Wall sample stopped; native chase unchanged.\n");}
}
bool RegisterWalkerCommands(){
    std::lock_guard lock(mutex);if(registered||!g_pCVar)return false;
    const char* names[]={"citadelcast_wall_start","citadelcast_wall_status","citadelcast_wall_stop"};
    const char* help[]={"Measure two native traces: watch chase offair <clear|wall|corner|floor>;3s countdown;no camera move.","Read/save native wall-query diagnostics;no camera change.","Cancel native wall-query countdown;native chase unchanged."};
    FnCommandCallback_t callbacks[]={Start,StatusCommand,Stop};
    for(const char* name:names)if(g_pCVar->FindConCommand(name,true).IsValidRef())return false;
    for(unsigned i=0;i<commands.size();++i){ConCommandCreation_t c{};c.m_pszName=names[i];c.m_pszHelpString=help[i];c.m_nFlags=FCVAR_RELEASE|FCVAR_CLIENTDLL;c.m_CBInfo=ConCommandCallbackInfo_t(callbacks[i]);commands[i]=g_pCVar->RegisterConCommand(c,0);
        if(!commands[i].IsValidRef()){for(auto& command:commands)if(command.IsValidRef()){g_pCVar->UnregisterConCommandCallbacks(command);command.InvalidateRef();}return false;}}
    registered=true;return true;
}
void ShutdownWalker(){
    std::lock_guard lock(mutex);shutting_down=true;session.finish(false,"shutdown");owner.store(0,std::memory_order_release);Save(true);
    for(auto it=hooks.rbegin();it!=hooks.rend();++it)if(!it->restore())Plat_FatalError("CitadelCast wall query could not restore owned callbacks.");
    for(auto& command:commands)if(command.IsValidRef()){if(g_pCVar)g_pCVar->UnregisterConCommandCallbacks(command);command.InvalidateRef();}
    registered=false;cheats.reset();director.reset();
}
