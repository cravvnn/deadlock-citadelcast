#pragma once
#include <cmath>
namespace wall_query {
class Budget {
    double began_;bool failed_=false;
public:
    explicit Budget(double t):began_(t),failed_(!std::isfinite(t)){}
    bool allowed(double t)const{return !failed_&&std::isfinite(t)&&t>=began_&&t-began_<=.010;}
    bool finish_call(double start,double end){
        if(!allowed(start)||!std::isfinite(end)||end<start||end-start>.002||!allowed(end))failed_=true;
        return !failed_;
    }
};
enum class Stage {Idle,Countdown,Sampling,Complete,Refused};
class Schedule {
    Stage state_=Stage::Idle;unsigned count_=0;bool pending_=false,blocked_=false;
    double began_=0,last_=0;const char* reason_="idle";
public:
    bool active()const{return state_==Stage::Countdown||state_==Stage::Sampling;}
    bool pending()const{return pending_;}
    bool blocked()const{return blocked_;}
    unsigned count()const{return count_;}
    Stage state()const{return state_;}
    const char* reason()const{return reason_;}
    double elapsed(double t)const{return t-began_;}
    void saved(){pending_=false;}
    bool arm(double t,bool gates){
        if(active()||pending_||blocked_||count_>=3||!gates||!std::isfinite(t))return false;
        ++count_;began_=last_=t;state_=Stage::Countdown;reason_="countdown";return true;
    }
    void finish(bool valid,const char* reason){
        if(!active())return;
        state_=valid?Stage::Complete:Stage::Refused;reason_=reason;pending_=true;blocked_=!valid;
    }
    bool due(double t,bool gates){
        if(!active())return false;
        if(!std::isfinite(t)||t<last_||t-began_>4){finish(false,"clock/deadline invalid");return false;}
        last_=t;
        if(!gates){finish(false,"viewer/focus/input/camera gate changed");return false;}
        if(t-began_<3)return false;
        state_=Stage::Sampling;reason_="sampling";return true;
    }
};
}
