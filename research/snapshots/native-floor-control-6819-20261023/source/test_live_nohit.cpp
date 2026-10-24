#include "query_contract.hpp"
#include <cstdio>
#include <cstring>
#include <stdexcept>
using namespace collision_contract;
template<class T>void put(RawResult& r,std::size_t at,const T& value){std::memcpy(r.bytes.data()+at,&value,sizeof(T));}
int main(){try{
    // Public numeric fields copied from the actual two returned native calls.
    const Vec3 start{-208.917419f,1028.93518f,424.f};
    const Vec3 end{-180.403641f,1172.24207f,431.831665f};
    const Context c{11,19267670,33,44,55,true,true,true,true,true,true,true,true};
    const std::array<Request,2> requests={Request{start,end,Kind::Line,0},Request{start,end,Kind::Sphere,8}};
    OneSample sample;sample.arm();std::array<Reading,2> result;unsigned calls=0;
    const bool ok=sample.run(requests,result,[&]{return c;},[&](const Request& q){
        ++calls;RawResult r;put(r,0x78,q.start);put(r,0x84,end);put(r,0xac,1.f);
        // Both output tags were0; flags and native hit booleans were false.
        return r;
    });
    if(!ok||calls!=2||result[0].outcome!=Outcome::NoContact||result[1].outcome!=Outcome::NoContact)
        throw std::runtime_error(sample.reason());
    std::puts("saved two-call native miss fixture accepted; sphere input1/default output0; no engine execution");
}catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
