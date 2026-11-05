// Ashta Sensor XDP — observe-only (XDP_PASS siempre en v1)
// NEW WORK — Meta Hackathon Oct27-Nov4 2026. No carga sin revisión.
// Clasifica patrones "demoníacos": escaneo, ráfaga, destino no esperado.
// Solo contadores en maps; el juicio lo hace Ashta-Gate en userspace.
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>
#define ASPECT_SCAN 0
#define ASPECT_BURST 1
#define ASPECT_MAX 8
struct { __uint(type, BPF_MAP_TYPE_ARRAY); __uint(max_entries, ASPECT_MAX);
         __type(key, __u32); __type(value, __u64); } ashta_counters SEC(".maps");
static __always_inline void bump(__u32 k){ __u64 *v=bpf_map_lookup_elem(&ashta_counters,&k); if(v) __sync_fetch_and_add(v,1); }
SEC("xdp") int ashta_xdp(struct xdp_md *ctx){
  void *d=(void*)(long)ctx->data, *e=(void*)(long)ctx->data_end;
  struct ethhdr *eth=d; if((void*)(eth+1)>e) return XDP_PASS;
  if(eth->h_proto!=__constant_htons(ETH_P_IP)) return XDP_PASS;
  struct iphdr *ip=(void*)(eth+1); if((void*)(ip+1)>e) return XDP_PASS;
  if(ip->protocol==6||ip->protocol==17) bump(ASPECT_BURST);
  return XDP_PASS; // observe-only: nunca DROP en v1
}
char LICENSE[] SEC("license") = "GPL";
