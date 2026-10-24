#include "follow_filter.hpp"
#include "follow_thread.hpp"
#include <cassert>
#include <cstdio>
#include <limits>
#include <future>

int main(){
    follow::Filter filter;follow::Pose zero{},target{};target[0]=100;
    assert(filter.begin(0,zero));assert(filter.advance(.25,target,true));
    assert(std::abs(filter.pose()[0]-100*(1-std::exp(-1)))<1e-11);
    for(unsigned rate:{60,144}){
        follow::Filter f;assert(f.begin(0,zero));
        for(unsigned i=1;i<=rate;++i)assert(f.advance(double(i)/rate,target,true));
        assert(std::abs(f.pose()[0]-100*(1-std::exp(-4)))<1e-10);
    }
    follow::Pose before{},after{};before[4]=179;after[4]=-179;
    follow::Filter yaw;assert(yaw.begin(0,before) && yaw.advance(.25,after,true));
    assert(std::abs(follow::Wrap(yaw.pose()[4]-179)-2*(1-std::exp(-1)))<1e-11);
    for(unsigned case_id=0;case_id<6;++case_id){
        follow::Filter f;assert(f.begin(1,zero));auto input=zero;double now=1.01;bool gate=true;
        if(case_id==0)now=.99;
        if(case_id==1)now=1.3;
        if(case_id==2)input[0]=513;
        if(case_id==3)input[4]=100;
        if(case_id==4)input[0]=NAN;
        if(case_id==5)gate=false;
        assert(!f.advance(now,input,gate) && !f.active());
        float output[3]={8,9,10};assert(!f.copy(output,0,true));
        assert(output[0]==8 && output[1]==9 && output[2]==10);
    }
    // Slow first update can exceed the lag bound even without a teleport.
    follow::Filter lag;assert(lag.begin(0,zero));target[0]=400;
    assert(!lag.advance(.001,target,true));
    float native[3]={11,12,13};assert(!filter.copy(native,0,false));assert(native[0]==11);
    assert(filter.copy(native,0,true) && native[0]>60 && native[0]<64);
    filter.stop("operator stop");assert(!filter.copy(native,0,true));
    assert(!filter.begin(NAN,zero));zero[2]=INFINITY;assert(!filter.begin(0,zero));
    std::atomic<DWORD> owner{GetCurrentThreadId()};std::recursive_mutex mutex;
    {
        std::lock_guard locked(mutex);
        auto worker=std::async(std::launch::async,[&]{
            return follow::ReadOnOwner(owner,mutex,[]{return 17;},[](int&){assert(false && "foreign output must stay native");});
        });
        assert(worker.wait_for(std::chrono::milliseconds(500))==std::future_status::ready);
        assert(worker.get()==17);
    }
    assert(follow::ReadOnOwner(owner,mutex,[]{return 17;},[](int& value){value=23;})==23);
    std::puts("follow_filter: analytic response, 60/144Hz partition, yaw wrap, sample/clock/discontinuity/lag gates and no writes after stop passed");
}
