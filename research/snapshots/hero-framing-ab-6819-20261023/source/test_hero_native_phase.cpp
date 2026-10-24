#include "hero_native_phase.hpp"
#include "hero_composition.hpp"
#include <cassert>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <cstdio>

struct Sample {
    unsigned identity=7;
    hero::Vec root{};
    bool same_identity(const Sample& other)const{return identity==other.identity;}
};
int Reversals(const std::vector<hero::Vec>& roots){
    int count=0;
    for(std::size_t i=2;i<roots.size();++i){
        double dot=0;for(unsigned n=0;n<3;++n)dot+=(roots[i][n]-roots[i-1][n])*(roots[i-1][n]-roots[i-2][n]);
        count+=dot<0;
    }
    return count;
}
int main(int argc,char** argv){
    assert(argc==2);std::ifstream input(argv[1]);assert(input);
    std::vector<hero::Vec> old_roots,new_roots;hero::FreshTargetSampler sampler;
    std::string line;Sample initial;unsigned calls=0;double last=-1;
    hero::Rig rig;
    while(std::getline(input,line)){
        if(line.empty()||line[0]=='#')continue;
        std::istringstream row(line);double now;Sample before,after;row>>now;
        for(auto& x:before.root)row>>x;for(auto& x:after.root)row>>x;assert(row&&now>last);last=now;
        Sample current=before,result;
        assert(sampler.sample(initial,result,[]{return true;},[&](Sample& out){out=current;return true;},
            [&](const Sample& target){assert(target.same_identity(initial));++calls;current=after;return true;}));
        assert(result.root==after.root);
        old_roots.push_back(before.root);new_roots.push_back(result.root);
        if(new_roots.size()==1)assert(rig.begin(now,result.root,20));else assert(rig.advance(now,result.root,true));
        assert(rig.focus()==hero::Focus(after.root));
    }
    assert(new_roots.size()==351 && calls==351 && sampler.samples==351 && sampler.refreshes==351);
    assert(Reversals(old_roots)==318 && Reversals(new_roots)==0);
    Sample result;result.root={111,222,333};const auto unchanged=result.root;
    for(unsigned failure=0;failure<8;++failure){
        sampler.reset();bool gate=true;unsigned reads=0,updates=0,gates=0;
        auto allowed=[&]{++gates;return gate&&failure!=0&&!(failure==7&&gates==4);};
        auto read=[&](Sample& out){++reads;out=initial;out.root={1,2,3};
            if((failure==1&&reads==1)||(failure==4&&reads==2))return false;
            if((failure==2&&reads==1)||(failure==5&&reads==2))out.identity=99;
            return true;};
        auto refresh=[&](const Sample&){++updates;if(failure==3)gate=false;return failure!=6;};
        assert(!sampler.sample(initial,result,allowed,read,refresh));assert(result.root==unchanged);
        assert(updates==(failure<=2?0u:1u));assert(sampler.samples==0);
    }
    sampler.reset();auto read=[](Sample& out){out.root={10,20,30};return true;};
    assert(sampler.sample(initial,result,[]{return true;},read,[&](const Sample&){
        Sample nested;
        assert(!sampler.sample(initial,nested,[]{return true;},read,[](const Sample&){assert(false);return true;}));return true;}));
    assert(sampler.samples==1&&sampler.refreshes==1&&sampler.refused==1);
    assert(result.root==hero::Vec({10,20,30}));
    std::puts("hero_native_phase: recorded351-row fixture reproduces318 pre-update reversals and0 post-update; native getter before fresh coherent target; stop/reentry/gate/read/identity refusals preserve output");
}
