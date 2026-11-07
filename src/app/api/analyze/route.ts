import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 10;

type OEmbed = { title?:string; author_name?:string; author_url?:string; thumbnail_url?:string; html?:string; provider_name?:string };

function validTikTokUrl(raw:string): URL | null {
  try {
    const u=new URL(raw);
    const host=u.hostname.toLowerCase().replace(/^www\./,"");
    if(u.protocol!=="https:" || !["tiktok.com","m.tiktok.com","vm.tiktok.com","vt.tiktok.com"].includes(host)) return null;
    return u;
  } catch { return null; }
}

export async function POST(req:NextRequest) {
  try {
    const body=await req.json();
    const raw=typeof body.url==="string"?body.url.trim():"";
    const url=validTikTokUrl(raw);
    if(!url) return NextResponse.json({error:"Enter a valid public TikTok HTTPS link."},{status:400});
    const notes=typeof body.notes==="string"?body.notes.slice(0,1200):"";
    let metadata:Record<string,unknown>={};
    let metadataAvailable=false;
    const endpoint=new URL("https://www.tiktok.com/oembed");
    endpoint.searchParams.set("url",url.toString());
    try {
      const upstream=await fetch(endpoint,{
        headers:{"Accept":"application/json","User-Agent":"TikTokIntelligenceSkill/0.2 (+public metadata lookup)"},
        signal:AbortSignal.timeout(4500),cache:"no-store"
      });
      if(upstream.ok){
        const data=(await upstream.json()) as OEmbed;
        metadata={title:data.title,authorName:data.author_name,authorUrl:data.author_url,thumbnailUrl:data.thumbnail_url,embedHtml:data.html,provider:data.provider_name};
        metadataAvailable=true;
      }
    } catch { /* Song retrieval runs independently through the media worker. */ }

    let analysis:string|undefined;
    if(metadataAvailable && process.env.GROQ_API_KEY){
      try{
        const ai=await fetch("https://api.groq.com/openai/v1/chat/completions",{
          method:"POST",
          headers:{"Authorization":`Bearer ${process.env.GROQ_API_KEY}`,"Content-Type":"application/json"},
          body:JSON.stringify({
            model:process.env.GROQ_MODEL||"llama-3.3-70b-versatile",
            temperature:0.2,
            messages:[
              {role:"system",content:"You are an evidence-first research analyst. Analyze only the supplied TikTok public metadata and user question. Never claim to have watched the video or infer actual scenes, audio, transcript, claims or intent. State what is unknown."},
              {role:"user",content:JSON.stringify({metadata,question:notes||"Give a concise professional context note based only on this metadata."})}
            ]
          }),
          signal:AbortSignal.timeout(4000)
        });
        if(ai.ok){const j=await ai.json();analysis=j.choices?.[0]?.message?.content;}
      } catch { /* Metadata and song-recognition paths remain available. */ }
    }
    return NextResponse.json({
      status:metadataAvailable?"metadata-available":"metadata-unavailable",
      sourceUrl:url.toString(),
      fetchedAt:new Date().toISOString(),
      metadata:metadataAvailable?metadata:undefined,
      analysis,
      limitations:[
        metadataAvailable?"oEmbed metadata was returned. It does not prove what is audible in the video.":"TikTok oEmbed metadata was unavailable; automatic media retrieval will still be attempted separately.",
        "The connected AI may perform wider video interpretation; this app's recognition report only claims evidence returned by the worker.",
        "TikTok may block, remove or restrict public media retrieval."
      ],
      nextSteps:["Song recognition runs as a separate asynchronous worker job.","If more than one 90-second segment is accessible, request continuation to check the next segment."]
    });
  } catch(e) {
    return NextResponse.json({error:e instanceof Error?e.message:"Unexpected analysis error."},{status:500});
  }
}
