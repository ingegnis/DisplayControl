import it.carisma.player.NetworkPolicy;
public class PolicyTest {
 static int n=0;
 static void check(boolean value){n++;if(!value)throw new AssertionError("Caso "+n);}
 static void rejects(String s){try{NetworkPolicy.server(s);throw new AssertionError("Accettato: "+s);}catch(IllegalArgumentException expected){n++;}}
 public static void main(String[] args){
  check(NetworkPolicy.server("192.168.1.10").equals("http://192.168.1.10:8787"));
  check(NetworkPolicy.server("https://10.0.0.2:9443/").equals("https://10.0.0.2:9443"));
  check(NetworkPolicy.server("172.16.0.1:8787").equals("http://172.16.0.1:8787"));
  for(String s:new String[]{"8.8.8.8","127.0.0.1","example.com","192.168.1.256","192.168.01.1","172.32.0.1","http://user@192.168.1.2","http://192.168.1.2/a","http://192.168.1.2?foo","http://192.168.1.2#foo","file://192.168.1.1","192.168.1.1:0","192.168.1.1:99999"})rejects(s);
  check(NetworkPolicy.allowed("/api/player/state","GET"));check(NetworkPolicy.allowed("/api/player/ndi/start","POST"));check(NetworkPolicy.allowed("/api/player/heartbeat","POST"));
  check(NetworkPolicy.allowed("/api/player/ndi/media/0123456789abcdef/abcdef0123456789/init.mp4","GET"));
  check(NetworkPolicy.allowed("/api/player/ndi/media/0123456789abcdef/abcdef0123456789/seg_000000001.m4s","GET"));
  for(String s:new String[]{"/api/state","/api/player/pair","/api/player/ndi/stop","/api/player/ndi/media/0123456789abcdef/abcdef0123456789/../../server.py","https://example.com"})check(!NetworkPolicy.allowed(s,"POST"));
  check(NetworkPolicy.allowed("/api/player/preview","POST"));
  check(!NetworkPolicy.allowed("/api/player/preview","GET"));
  check(!NetworkPolicy.allowed("/api/monitor","GET"));
  check(!NetworkPolicy.allowed("/api/player/state","PUT"));
  System.out.println(n+" controlli policy Java: OK (non test Android)");
 }
}
