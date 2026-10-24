#pragma once
#include <array>
#include <cmath>
#include <cstdint>
namespace phase_probe {
enum class State { Idle, Countdown, Sampling, Complete, Refused };
struct Row {
    double elapsed=0,native_ms=0,read_ms=0;
    unsigned observer_updates=0;
    bool before_valid=false,after_valid=false,same_world=false,same_target=false;
    bool main_before=false,main_after=false;
    // Native globals+0x30 is absolute curtime. Frame duration is at+0x34;
    // the native observer only requires curtime>0, with simulation flag clear.
    float curtime_before=0,curtime_after=0;
    std::uint32_t handle_before=0,handle_after=0;
    std::array<float,3> camera_before{},camera_after{},root_before{},root_after{};
};
class Session {
    State state_=State::Idle;bool used_=false;
    double began_=0,last_=0;
    const char* reason_="idle";
    std::array<Row,4> rows_{};unsigned count_=0;
public:
    State state()const{return state_;}
    bool active()const{return state_==State::Countdown||state_==State::Sampling;}
    bool used()const{return used_;}
    unsigned count()const{return count_;}
    const auto& rows()const{return rows_;}
    const char* reason()const{return reason_;}
    double elapsed(double now)const{return now-began_;}
    void cancel(const char* why){if(active()){state_=State::Refused;reason_=why;}}
    bool arm(double now,bool gates){
        if(used_||!gates||!std::isfinite(now))return false;
        used_=true;began_=last_=now;state_=State::Countdown;reason_="countdown";return true;
    }
    bool before(double now,bool gates){
        if(!active())return false;
        if(!std::isfinite(now)||now<last_){cancel("clock invalid");return false;}
        last_=now;
        if(!gates){cancel("viewer/focus/input/camera gate changed");return false;}
        if(now-began_>4){cancel("sample deadline exceeded");return false;}
        if(now-began_<3)return false;
        state_=State::Sampling;reason_="sampling";return true;
    }
    void submit(double now,Row row){
        if(state_!=State::Sampling)return;
        row.elapsed=now-began_;
        if(count_>=rows_.size()){cancel("sample bound exceeded");return;}
        rows_[count_++]=row;
        if(!std::isfinite(now)||now<last_||row.elapsed>4){cancel("sample clock/deadline changed");return;}
        last_=now;
        if(!row.before_valid||!row.after_valid){cancel("snapshot refused");return;}
        if(!row.main_before||!row.main_after){cancel("native main-thread check failed");return;}
        if(!row.same_world){cancel("world absent or changed across native frame");return;}
        if(!row.same_target||row.handle_before!=row.handle_after){cancel("selected hero changed across native frame");return;}
        if(row.observer_updates!=1){cancel("expected one selected observer update");return;}
        if(!std::isfinite(row.curtime_before)||!std::isfinite(row.curtime_after)||
           row.curtime_before<=0||row.curtime_after<=0){
            cancel("native current time invalid or nonpositive");return;
        }
        if(!std::isfinite(row.native_ms)||!std::isfinite(row.read_ms)||row.native_ms<0||row.read_ms<0||row.read_ms>10){
            cancel("probe read budget exceeded or invalid");return;
        }
        if(count_==rows_.size()){state_=State::Complete;reason_="four native frames observed; no physics queries";}
    }
};
// The native frame always runs exactly once, even when sampling is refused.
// Snapshot readers are only invoked for an explicitly armed due sample.
template<class Native,class Before,class After>
void Frame(bool sample,Native native,Before before,After after){
    if(sample)before();
    native();
    if(sample)after();
}
}
