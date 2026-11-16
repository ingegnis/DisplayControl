/* Test fixture only. NOT NDI: no network protocol or proprietary codec.
 * Builds a tiny fake ABI to exercise our ctypes buffer ownership and FFmpeg path.
 * gcc -shared -fPIC tests/fake_ndi.c -o /tmp/carisma_fake_ndi.so -lm
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
typedef struct { const char *name, *url; } Source;
typedef struct { bool local; const char *groups, *ips; } Find;
typedef struct { Source source; int color, bandwidth; bool fields; const char *name; } Recv;
typedef struct { int width,height; uint32_t fourcc; int fps_n,fps_d; float aspect;
 int frame_format; int64_t timecode; void *data; int stride; const char *metadata; int64_t timestamp; } Video;
typedef struct { int rate,channels,samples; int64_t timecode; void *data; int stride; const char *metadata; int64_t timestamp; } Audio;
typedef struct { int64_t video,audio,metadata; } Perf;
typedef struct { unsigned char *pixels; float *audio; int64_t video_count,audio_count,samples; double last; int64_t stamp; } State;
static Source source={"CARISMA TEST (ABI NON NDI)","127.0.0.1:0"};
static double now(void){
#ifdef _WIN32
 LARGE_INTEGER counter, frequency;QueryPerformanceCounter(&counter);QueryPerformanceFrequency(&frequency);return (double)counter.QuadPart/frequency.QuadPart;
#else
 struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;
#endif
}
static bool signal_on(void){const char *path=getenv("CARISMA_FAKE_SIGNAL_FILE");if(!path)return true;FILE *f=fopen(path,"r");if(!f)return true;int c=fgetc(f);fclose(f);return c!='0';}
EXPORT bool NDIlib_initialize(void){return true;}
EXPORT void NDIlib_destroy(void){}
EXPORT const char *NDIlib_version(void){return "TEST ABI / NON NDI";}
EXPORT void *NDIlib_find_create_v2(const Find *f){return (void*)&source;}
EXPORT const Source *NDIlib_find_get_current_sources(void *f,uint32_t *count){*count=1;return &source;}
EXPORT void NDIlib_find_destroy(void *f){}
EXPORT void *NDIlib_recv_create_v3(const Recv *r){State *s=calloc(1,sizeof(State));s->pixels=calloc(1,(640*4+16)*360);s->audio=calloc(1920,sizeof(float));return s;}
EXPORT void NDIlib_recv_destroy(void *v){State*s=v;free(s->pixels);free(s->audio);free(s);}
EXPORT void *NDIlib_framesync_create(void *r){return r;}
EXPORT void NDIlib_framesync_destroy(void *s){}
EXPORT void NDIlib_recv_get_performance(void *v,Perf *total,Perf *drop){State*s=v;*total=(Perf){s->video_count,s->audio_count,0};*drop=(Perf){0,0,0};}
EXPORT int NDIlib_recv_get_no_connections(void *v,uint32_t timeout){return signal_on()?1:0;}
EXPORT void NDIlib_framesync_capture_video(void *v,Video *f,int type){State*s=v;double t=now();
 if(signal_on()&&t-s->last>=1.0/30){s->last=t;s->video_count++;s->stamp=(int64_t)(t*1e7);
  for(int y=0;y<360;y++)for(int x=0;x<640;x++){unsigned char*p=s->pixels+y*(640*4+16)+x*4;p[0]=(x+s->video_count*2)%256;p[1]=(y+30)%256;p[2]=(x/80)%2?220:25;p[3]=255;}}
 *f=(Video){640,360,0x58524742,30,1,16.0f/9,1,s->stamp,s->pixels,640*4+16,NULL,s->stamp};}
EXPORT void NDIlib_framesync_free_video(void *s,Video*f){memset(f,0,sizeof(*f));}
EXPORT void NDIlib_framesync_capture_audio(void *v,Audio*f,int rate,int channels,int samples){State*s=v;
 bool on=signal_on();
 for(int i=0;i<samples;i++){float sample=on?0.02f*sinf(2*3.14159265*440*(s->samples+i)/48000.0):0;s->audio[i]=sample;s->audio[samples+i]=sample;}s->samples+=samples;s->audio_count++;
 *f=(Audio){48000,2,samples,0,s->audio,samples*4,NULL,s->stamp};}
EXPORT void NDIlib_framesync_free_audio(void*s,Audio*f){memset(f,0,sizeof(*f));}
