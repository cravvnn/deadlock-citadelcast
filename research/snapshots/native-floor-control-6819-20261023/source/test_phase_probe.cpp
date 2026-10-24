#include "phase_probe.hpp"
#include <cstdio>
#include <limits>
#include <stdexcept>
using namespace phase_probe;
void check(bool b,const char* why="phase probe assertion"){if(!b)throw std::runtime_error(why);}
Row Good(){Row r;r.before_valid=r.after_valid=r.same_world=r.same_target=r.main_before=r.main_after=true;
    r.observer_updates=1;r.curtime_before=r.curtime_after=.01f;r.handle_before=r.handle_after=42;r.native_ms=1;r.read_ms=.1;return r;}
int main(){try{
    unsigned n=0;auto test=[&](const char* name,auto body){body();++n;std::printf("PASS %s\n",name);};
    test("four frames complete without rearm",[]{Session s;check(s.arm(10,true));check(!s.arm(10,true));check(!s.before(12.99,true));for(int k=0;k<4;++k){check(s.before(13+k*.01,true));s.submit(13+k*.01,Good());}check(s.state()==State::Complete&&s.count()==4&&!s.arm(20,true));});
    test("native runs once when not sampling",[]{int native=0,reads=0;Frame(false,[&]{++native;},[&]{++reads;},[&]{++reads;});check(native==1&&reads==0);});
    test("native is between two snapshot stages",[]{int sequence=0;Frame(true,[&]{check(sequence++==1);},[&]{check(sequence++==0);},[&]{check(sequence++==2);});check(sequence==3);});
    test("countdown gate loss stops",[]{Session s;check(s.arm(1,true));check(!s.before(2,false));check(!s.before(4,true)&&s.state()==State::Refused&&s.count()==0);});
    test("deadline no retries",[]{Session s;check(s.arm(1,true));check(!s.before(5.1,true));check(!s.arm(6,true));});
    test("clock backward and NaN",[]{for(double t:{.9,std::numeric_limits<double>::quiet_NaN()}){Session s;check(s.arm(1,true));check(!s.before(t,true)&&s.state()==State::Refused);}});
    test("world change refuses",[]{Session s;s.arm(1,true);s.before(4,true);auto r=Good();r.same_world=false;s.submit(4,r);check(s.state()==State::Refused&&s.count()==1);});
    test("selected identity change refuses",[]{Session s;s.arm(1,true);s.before(4,true);auto r=Good();r.same_target=false;s.submit(4,r);check(s.state()==State::Refused);});
    test("missing or repeated native observer refuses",[]{for(unsigned c:{0u,2u}){Session s;s.arm(1,true);s.before(4,true);auto r=Good();r.observer_updates=c;s.submit(4,r);check(s.state()==State::Refused);}});
    test("missing snapshot and foreign main thread refuse",[]{for(auto field:{&Row::before_valid,&Row::after_valid,&Row::main_before,&Row::main_after}){Session s;s.arm(1,true);s.before(4,true);auto r=Good();r.*field=false;s.submit(4,r);check(s.state()==State::Refused);}});
    test("invalid native current time and slow reads refuse",[]{for(int i=0;i<3;++i){Session s;s.arm(1,true);s.before(4,true);auto r=Good();if(i==0)r.curtime_before=0;if(i==1)r.curtime_after=std::numeric_limits<float>::infinity();if(i==2)r.read_ms=10.1;s.submit(4,r);check(s.state()==State::Refused);}});
    test("operator cancellation has no further sample",[]{Session s;s.arm(1,true);s.cancel("operator stop");check(!s.before(4,true));s.submit(4,Good());check(s.count()==0);});
    test("failed initial gate never uses session",[]{Session s;check(!s.arm(1,false)&&!s.used());check(s.arm(2,true));});
    test("reported310second curtime is not a frame interval",[]{Session s;check(s.arm(1,true));for(int i=0;i<4;++i){const double t=4+i*.01;check(s.before(t,true));auto r=Good();r.curtime_before=r.curtime_after=310.369354f;r.read_ms=.423900001;r.native_ms=.132699999;s.submit(t,r);}check(s.state()==State::Complete&&s.count()==4,"reported310second curtime falsely refused");});
    test("late match absolute clocks remain eligible",[]{Session s;s.arm(1,true);s.before(4,true);auto r=Good();r.curtime_before=r.curtime_after=10000.f;s.submit(4,r);check(s.state()==State::Sampling,"late absolute clock falsely refused");});
    std::printf("%u phase-probe scenarios passed\n",n);
}catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
