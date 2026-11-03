package br.com.z1prospectia;
import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebChromeClient;
import android.widget.LinearLayout;
import android.widget.EditText;
import android.widget.Button;
import android.widget.TextView;
import android.text.InputType;
public class MainActivity extends Activity {
 private static final String DEFAULT_URL="https://z1-prospect-ia.onrender.com";
 private WebView web;
 @Override public void onCreate(Bundle state){super.onCreate(state);open(getPreferences(MODE_PRIVATE).getString("server_url",DEFAULT_URL));}
 private void setup(){
  LinearLayout l=new LinearLayout(this);l.setOrientation(1);l.setPadding(32,48,32,24);
  TextView t=new TextView(this);t.setText("Z1 Prospect IA — Configurar servidor HTTPS");t.setTextSize(20);l.addView(t);
  EditText e=new EditText(this);e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);e.setText(getPreferences(MODE_PRIVATE).getString("server_url",DEFAULT_URL));l.addView(e);
  TextView status=new TextView(this);l.addView(status);
  Button b=new Button(this);b.setText("Conectar");b.setOnClickListener(v->{String url=e.getText().toString().trim();Uri u=Uri.parse(url);if(!"https".equalsIgnoreCase(u.getScheme())||u.getHost()==null){status.setText("Informe URL HTTPS válida");return;}getPreferences(MODE_PRIVATE).edit().putString("server_url",url).apply();open(url);});l.addView(b);setContentView(l);
 }
 private void open(String url){
  LinearLayout l=new LinearLayout(this);l.setOrientation(1);
  Button settings=new Button(this);settings.setText("⚙ Alterar servidor");settings.setOnClickListener(v->setup());l.addView(settings);
  web=new WebView(this);web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.setWebChromeClient(new WebChromeClient());
  final String host=Uri.parse(url).getHost();
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req){
    Uri target=req.getUrl();if("https".equalsIgnoreCase(target.getScheme())&&host!=null&&host.equalsIgnoreCase(target.getHost()))return false;
    if("https".equalsIgnoreCase(target.getScheme())||"mailto".equalsIgnoreCase(target.getScheme())){try{startActivity(new Intent(Intent.ACTION_VIEW,target));}catch(Exception ignored){}}return true;
   }
  });
  l.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(l);web.loadUrl(url);
 }
 @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
}