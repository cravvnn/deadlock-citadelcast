#include "hero_motion_trace.hpp"
#include <cassert>
#include <memory>
#include <limits>
int main(int argc,char**argv){
    assert(argc==2);auto trace=std::make_unique<hero_motion::Trace>();hero_motion::Row row{};
    row[0]=100;row[1]=1;row[2]=15;row[3]=1;row[6]=2;row[9]=3;row[15]=4;
    const auto original=row;assert(!trace->append(row,true));trace->reset(100);
    assert(!trace->append(row,false)&&trace->size()==0);
    assert(trace->append(row,true)&&trace->size()==1&&row==original);
    row[0]=100.01;row[1]=2;row[2]=31;row[21]=7;row[24]=1;row[26]=.01;
    assert(trace->append(row,true)&&trace->size()==2);
    row[0]=100.02;row[26]=1;row[24]=2;assert(trace->append(row,true));
    for(unsigned fault=0;fault<5;++fault){
        auto bad=row;if(fault==0)bad[0]=99;if(fault==1)bad[0]=100;if(fault==2)bad[1]=0;if(fault==3)bad[2]=32;if(fault==4)bad[3]=NAN;
        assert(!trace->append(bad,true)&&trace->size()==3);
    }
    trace->stop();assert(!trace->append(row,true)&&trace->size()==3);
    FILE*out=nullptr;assert(fopen_s(&out,argv[1],"wb")==0);std::fputs("{\"closed\":",out);trace->write(out,true);
    std::fputs(",\"during_take\":",out);trace->write(out,false);std::fputs("}\n",out);std::fclose(out);
    trace->reset(0);row={};row[1]=2;
    // An explicit overflow counter protects memory bounds; old rows are not
    // overwritten and reset/invalid clock never expose earlier take contents.
    for(unsigned n=0;n<8192;++n){row[0]=n*.001;assert(trace->append(row,true));}
    row[0]=9;assert(!trace->append(row,true)&&trace->size()==8192&&trace->dropped()==1);
    trace->reset(NAN);assert(trace->size()==0&&!trace->append(row,true));
    trace->reset(-std::numeric_limits<double>::max());row[0]=std::numeric_limits<double>::max();assert(!trace->append(row,true)&&trace->size()==0);
    trace->reset(20);row[0]=20;assert(trace->append(row,true)&&trace->size()==1);
    std::puts("motion_trace: readonly numeric input, explicit phase/validity flags, monotonic clock, sealed/no-owner refusal,8192sample bound/reset and no during-take row serialization passed");
}
