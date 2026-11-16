package it.carisma.player;
import java.net.URI;
/** Pure Java validation, also tested on a desktop JDK. No DNS resolution. */
public final class NetworkPolicy {
    private NetworkPolicy() {}
    public static String server(String raw) {
        if (raw == null) throw new IllegalArgumentException("Indirizzo mancante");
        String value = raw.trim();
        if (!value.contains("://")) value = "http://" + value;
        URI u = URI.create(value);
        if (!("http".equals(u.getScheme()) || "https".equals(u.getScheme())) || u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null)
            throw new IllegalArgumentException("Usa un IP LAN, senza credenziali o percorso");
        if (u.getPath()!=null && !u.getPath().isEmpty() && !u.getPath().equals("/"))
            throw new IllegalArgumentException("Non aggiungere percorsi all'indirizzo del server");
        String h = u.getHost();
        if (h == null || !h.matches("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+"))
            throw new IllegalArgumentException("Usa l'indirizzo IPv4 del PC, esempio 192.168.1.20:8787");
        String[] parts = h.split("\\."); int[] ip = new int[4];
        for (int i=0;i<4;i++) {
            if (parts[i].length()>3 || (parts[i].length()>1 && parts[i].startsWith("0"))) throw new IllegalArgumentException("IPv4 non valido");
            ip[i]=Integer.parseInt(parts[i]);
            if(ip[i]>255) throw new IllegalArgumentException("IPv4 non valido");
        }
        if (!(ip[0]==10 || (ip[0]==192 && ip[1]==168) || (ip[0]==172 && ip[1]>=16 && ip[1]<=31)))
            throw new IllegalArgumentException("Questa versione accetta solo IPv4 di reti private");
        int port=u.getPort()==-1?8787:u.getPort();
        if(port<1||port>65535) throw new IllegalArgumentException("Porta non valida");
        return u.getScheme()+"://"+h+":"+port;
    }
    public static boolean allowed(String path, String method) {
        if(path==null) return false;
        if("POST".equals(method)) return path.equals("/api/player/preview") || path.equals("/api/player/heartbeat") || path.equals("/api/player/ndi/start");
        if(!"GET".equals(method)) return false;
        return path.equals("/api/player/state") || path.matches("/api/player/assets/[a-f0-9]{64}") ||
            path.matches("/api/player/ndi/manifest/[a-f0-9]{16}") ||
            path.matches("/api/player/ndi/media/[a-f0-9]{16}/[a-f0-9]{16}/(init\\.mp4|seg_[0-9]{9}\\.m4s)");
    }
}
