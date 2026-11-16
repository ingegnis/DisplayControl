package it.carisma.player;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebStorage;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.text.InputType;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;

/** Offline shell: only bundled HTML executes; remote server supplies JSON/media.
 * No shared admin secret, remote code, Google Play Services or file URL permissions.
 * Physical-device and Android SDK compilation validation still required.
 */
public class MainActivity extends Activity {
    private static final String ORIGIN="https://appassets.androidplatform.net";
    private SharedPreferences prefs;
    private WebView web;
    private volatile String base="", secret="", screen="";
    private TextView status;
    private boolean settings=false;
    private final ThreadPoolExecutor workers=new ThreadPoolExecutor(2,2,20,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(16));

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        prefs=getSharedPreferences("carisma",MODE_PRIVATE);
        base=prefs.getString("server","");secret=prefs.getString("token","");screen=prefs.getString("screen","");
        if(base.isEmpty()||secret.isEmpty()||screen.isEmpty()) showSetup(); else showPlayer();
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Color.rgb(237,236,217));t.setPadding(0,dp(8),0,dp(8));return t;}
    private void destroyWeb(){if(web!=null){web.removeJavascriptInterface("CarismaDevice");web.stopLoading();web.destroy();web=null;}}
    private void showSetup(){
        settings=true;destroyWeb();
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(Color.rgb(19,47,41));
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(dp(60),dp(20),dp(60),dp(20));box.setGravity(Gravity.CENTER_VERTICAL);scroll.addView(box);
        box.addView(text("CARISMA / COLLEGA PLAYER",27));
        box.addView(text("Nella regia: Collega player fisici > scegli schermo > genera codice.",16));
        final EditText host=new EditText(this);host.setSingleLine();host.setTextColor(Color.WHITE);host.setHintTextColor(Color.LTGRAY);host.setHint("192.168.1.20:8787");host.setText(base);host.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);box.addView(text("Indirizzo LAN del server (non quello del Chromecast)",14));box.addView(host);
        final EditText code=new EditText(this);code.setSingleLine();code.setTextColor(Color.WHITE);code.setHintTextColor(Color.LTGRAY);code.setHint("Codice di 8 cifre");code.setInputType(InputType.TYPE_CLASS_NUMBER);box.addView(code);
        final Button pair=new Button(this);pair.setText("ABBINA E AVVIA");box.addView(pair);
        status=text("La prima sincronizzazione richiede la LAN. Nessuna connessione Internet richiesta dall'app.",14);box.addView(status);
        pair.setOnClickListener(new View.OnClickListener(){public void onClick(View v){
            final String target;final String digits=code.getText().toString().trim();
            try{target=NetworkPolicy.server(host.getText().toString());if(!digits.matches("[0-9]{8}"))throw new IllegalArgumentException("Inserisci il codice di 8 cifre");}
            catch(Exception e){status.setText(e.getMessage());return;}
            pair.setEnabled(false);status.setText("Abbinamento in corso...");
            workers.execute(new Runnable(){public void run(){try{
                JSONObject request=new JSONObject();request.put("code",digits);request.put("name",android.os.Build.MODEL);
                HttpURLConnection c=connection(target,"/api/player/pair","POST","");writeBody(c,request.toString());
                int code=c.getResponseCode();String result=readText(code<400?c.getInputStream():c.getErrorStream(),1024*128);c.disconnect();
                final JSONObject data=new JSONObject(result);if(code!=201)throw new IOException(data.optString("error","Abbinamento non riuscito"));
                final String newSecret=data.getString("token"),newScreen=data.getString("screenId");
                if(!newScreen.matches("[A-Za-z0-9_-]{1,120}")||newSecret.length()<20)throw new IOException("Risposta server non valida");
                runOnUiThread(new Runnable(){public void run(){
                    // Re-pairing deliberately removes cached programs from a previous installation.
                    WebStorage.getInstance().deleteAllData();
                    base=target;secret=newSecret;screen=newScreen;
                    prefs.edit().putString("server",base).putString("token",secret).putString("screen",screen).commit();
                    showPlayer();
                }});
            }catch(final Exception e){runOnUiThread(new Runnable(){public void run(){if(status!=null)status.setText("Errore: "+e.getMessage());pair.setEnabled(true);}});}}});
        }});
        if(!secret.isEmpty()){Button back=new Button(this);back.setText("TORNA AL PLAYER ESISTENTE");box.addView(back);back.setOnClickListener(new View.OnClickListener(){public void onClick(View v){showPlayer();}});}
        setContentView(scroll);host.requestFocus();
    }
    private void immersive(){getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);}
    private void showPlayer(){
        settings=false;destroyWeb();web=new WebView(this);web.setBackgroundColor(Color.BLACK);
        WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setAllowFileAccessFromFileURLs(false);s.setAllowUniversalAccessFromFileURLs(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setMediaPlaybackRequiresUserGesture(false);s.setSupportMultipleWindows(false);
        CookieManager.getInstance().setAcceptCookie(false);web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new Bridge(),"CarismaDevice");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return true;}
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri u=request.getUrl();String p=u.getPath();
                if(!"https".equals(u.getScheme())||!"appassets.androidplatform.net".equals(u.getHost())||u.getPort()!=-1)return error(403,"Origine non consentita");
                try{
                    if("/player.html".equals(p))return asset("player.html","text/html");
                    if("/branding.js".equals(p))return asset("branding.js","text/javascript");
                    if("/physical_boot.js".equals(p))return asset("physical_boot.js","text/javascript");
                    if("/favicon.svg".equals(p))return asset("favicon.svg","image/svg+xml");
                    if(u.getQuery()!=null||!NetworkPolicy.allowed(p,request.getMethod()))return error(403,"Richiesta non consentita");
                    final HttpURLConnection c=connection(base,p,"GET",secret);
                    int code=c.getResponseCode();
                    if(code>=300 && code<400){c.disconnect();return error(502,"Redirect non consentito");}
                    InputStream in=code<400?c.getInputStream():c.getErrorStream();
                    if(in==null)in=new ByteArrayInputStream(new byte[0]);
                    final InputStream original=in;
                    InputStream managed=new FilterInputStream(original){@Override public void close()throws IOException{try{super.close();}finally{c.disconnect();}}};
                    String mime=c.getContentType();if(mime==null)mime="application/octet-stream";mime=mime.split(";")[0];
                    Map<String,String> headers=new HashMap<String,String>();headers.put("Cache-Control","no-store");
                    return new WebResourceResponse(mime,mime.contains("json")?"UTF-8":null,code,"Carisma",headers,managed);
                }catch(Exception e){return error(503,"Server non raggiungibile");}
            }
        });
        setContentView(web);immersive();web.loadUrl(ORIGIN+"/player.html?player="+Uri.encode(screen)+"&kiosk=1");
    }
    private WebResourceResponse asset(String name,String mime)throws IOException{
        Map<String,String> h=new HashMap<String,String>();h.put("Content-Security-Policy","default-src 'self' blob: data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:");
        return new WebResourceResponse(mime,"UTF-8",200,"OK",h,getAssets().open(name));
    }
    private WebResourceResponse error(int code,String message){return new WebResourceResponse("application/json","UTF-8",code,"Carisma",new HashMap<String,String>(),new ByteArrayInputStream(("{\"error\":"+JSONObject.quote(message)+"}").getBytes(StandardCharsets.UTF_8)));}
    private static HttpURLConnection connection(String server,String path,String method,String token)throws IOException{
        HttpURLConnection c=(HttpURLConnection)new URL(server+path).openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(4000);c.setReadTimeout(15000);c.setRequestMethod(method);c.setUseCaches(false);
        if(!token.isEmpty())c.setRequestProperty("X-Player-Token",token);return c;
    }
    private static void writeBody(HttpURLConnection c,String body)throws IOException{byte[] bytes=body.getBytes(StandardCharsets.UTF_8);c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(bytes.length);try(java.io.OutputStream out=c.getOutputStream()){out.write(bytes);}}
    private static String readText(InputStream in,int max)throws IOException{
        if(in==null)return "{}";try(InputStream src=in;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=src.read(b))!=-1){if(out.size()+n>max)throw new IOException("Risposta troppo grande");out.write(b,0,n);}return new String(out.toByteArray(),StandardCharsets.UTF_8);}
    }
    private final class Bridge{
        @JavascriptInterface public void request(final String id,final String path,final String body){
            if(id==null||!id.matches("[0-9]{1,12}"))return;
            if(!NetworkPolicy.allowed(path,"POST")||body==null||body.length()>("/api/player/preview".equals(path)?100000:65536)){respond(id,403,"{\"error\":\"Richiesta non consentita\"}");return;}
            try{workers.execute(new Runnable(){public void run(){HttpURLConnection c=null;try{c=connection(base,path,"POST",secret);writeBody(c,body);int code=c.getResponseCode();String result=readText(code<400?c.getInputStream():c.getErrorStream(),1024*256);respond(id,code>=300&&code<400?502:code,result);}catch(Exception e){respond(id,503,"{\"error\":\"Server non raggiungibile\"}");}finally{if(c!=null)c.disconnect();}}});}
            catch(Exception e){respond(id,503,"{\"error\":\"Troppe richieste\"}");}
        }
    }
    private void respond(final String id,final int code,final String body){runOnUiThread(new Runnable(){public void run(){if(web!=null)web.evaluateJavascript("window.CarismaNativeResult("+JSONObject.quote(id)+","+code+","+JSONObject.quote(body)+")",null);}});}
    @Override public void onBackPressed(){
        if(settings){if(!secret.isEmpty())showPlayer();else super.onBackPressed();return;}
        new AlertDialog.Builder(this).setTitle("Carisma Player").setItems(new String[]{"Riprendi","Audio attivo/disattivo","Diagnostica sullo schermo","Ricarica player","Nuovo abbinamento","Esci"},new DialogInterface.OnClickListener(){public void onClick(DialogInterface d,int which){
            if(which==1&&web!=null)web.evaluateJavascript("document.querySelector('[data-action=player-audio]')?.click()",null);
            if(which==2&&web!=null)web.evaluateJavascript("document.body.classList.toggle('kiosk')",null);
            if(which==3)showPlayer();
            if(which==4)showSetup();
            if(which==5)finish();
        }}).show();
    }
    @Override public void onWindowFocusChanged(boolean hasFocus){super.onWindowFocusChanged(hasFocus);if(hasFocus&&!settings)immersive();}
    @Override protected void onResume(){super.onResume();if(web!=null)web.onResume();}
    @Override protected void onPause(){if(web!=null)web.onPause();super.onPause();}
    @Override protected void onDestroy(){destroyWeb();workers.shutdownNow();super.onDestroy();}
}
