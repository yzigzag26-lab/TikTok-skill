"use client";
import { useState } from "react";

type SongMatch = { title?:string|null; artist?:string|null; album?:string|null; release_date?:string|null; song_link?:string|null; matched_at_seconds?:number; provider?:string };
type SongResult = { status:string; matches:SongMatch[]; message?:string; samples_checked?:number };
type Job = { id:string; status:string; result?:{ song_recognition?:SongResult; next_cursor?:string|null; status?:string; segment?:{start_seconds:number;end_seconds:number} }; error?:string };
type Report = { status:string; sourceUrl:string; fetchedAt:string; metadata?:{title?:string;authorName?:string;authorUrl?:string;thumbnailUrl?:string}; analysis?:string; limitations:string[]; nextSteps:string[] };

export default function Home(){
 const [url,setUrl]=useState("");
 const [notes,setNotes]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [report,setReport]=useState<Report|null>(null);
 const [songStatus,setSongStatus]=useState("idle");
 const [songResult,setSongResult]=useState<SongResult|null>(null);
 const [nextCursor,setNextCursor]=useState<string|null>(null);

 async function runSongJob(payload:{url?:string;cursor?:string}){
   setSongStatus("queued");if(payload.url)setSongResult(null);setNextCursor(null);setError("");
   try{
     const started=await fetch("/api/song-jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
     const startData=await started.json();
     if(!started.ok)throw new Error(startData.error||"Could not start song identification.");
     setSongStatus("processing");
     for(let i=0;i<150;i++){
       await new Promise(resolve=>setTimeout(resolve,2000));
       const response=await fetch("/api/song-jobs?jobId="+encodeURIComponent(startData.job_id),{cache:"no-store"});
       const job:Job=await response.json();
       if(!response.ok)throw new Error(job.error||"Could not retrieve song-identification status.");
       if(job.status==="failed")throw new Error(job.error||"Song identification failed.");
       if(job.status==="complete"&&job.result){
         const incoming=job.result.song_recognition||null;
         setSongResult(previous=>{
           if(!incoming)return previous;
           if(!payload.cursor||!previous)return incoming;
           const merged=[...previous.matches];
           for(const candidate of incoming.matches||[]){
             const exists=merged.some(item=>(item.title||"").toLowerCase()===(candidate.title||"").toLowerCase()&&(item.artist||"").toLowerCase()===(candidate.artist||"").toLowerCase());
             if(!exists)merged.push(candidate);
           }
           return {...incoming,matches:merged,samples_checked:(previous.samples_checked||0)+(incoming.samples_checked||0)};
         });
         setNextCursor(job.result.next_cursor||null);
         setSongStatus("complete");
         return;
       }
     }
     throw new Error("Song identification is taking longer than expected. You can retry without losing the TikTok link.");
   }catch(e){
     setSongStatus("failed");
     setError(e instanceof Error?e.message:"Song identification failed.");
   }
 }

 async function submit(e:React.FormEvent){
   e.preventDefault();setBusy(true);setError("");setReport(null);setSongResult(null);setNextCursor(null);setSongStatus("idle");
   try{
     const res=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,notes})});
     const data=await res.json();
     if(!res.ok)throw new Error(data.error||"TikTok link lookup failed.");
     setReport(data);
     await runSongJob({url});
   }catch(err){setError(err instanceof Error?err.message:"Something went wrong");}
   finally{setBusy(false);}
 }

 return <main className="shell">
 <nav className="nav"><div className="brand"><span className="brand-mark">T</span><span>TIKTOK <b>INTELLIGENCE</b></span></div><span className="nav-tag">SONG RECOGNITION <i/></span></nav>
 <section className="hero">
 <div className="eyebrow"><span/> EVIDENCE-FIRST MUSIC IDENTIFICATION</div>
 <h1>Find the song.<br/><em>Know what you&apos;re hearing.</em></h1>
 <p className="intro">Paste a public TikTok link. The service retrieves accessible audio, checks multiple short audio windows against a music-recognition database, and returns song candidates with timestamps and source links. Your connected AI can handle the wider video analysis.</p>
 <form className="analyze-card" onSubmit={submit}>
 <label htmlFor="tiktok-url">PUBLIC TIKTOK VIDEO URL</label>
 <div className="url-row"><input id="tiktok-url" type="url" placeholder="https://www.tiktok.com/@creator/video/..." value={url} onChange={e=>setUrl(e.target.value)} required/><button disabled={busy}>{busy?"WORKING…":"IDENTIFY SONG ↗"}</button></div>
 <label htmlFor="notes" className="notes-label">OPTIONAL QUESTION FOR VIDEO CONTEXT</label>
 <textarea id="notes" rows={2} placeholder="Optional context for the connected AI…" value={notes} onChange={e=>setNotes(e.target.value)}/>
 <div className="card-foot"><span>PUBLIC LINKS ONLY · NO LOGIN BYPASS</span><span>10 MB / 90 SEC SEGMENTS</span></div>
 </form>
 {error&&<div className="error">{error}</div>}
 {report&&<section className="report">
 <div className="report-head"><div><div className="eyebrow">SOURCE CHECK</div><h2>Video metadata</h2></div><span className="status">{report.status}</span></div>
 {report.metadata&&<div className="metadata">{report.metadata.thumbnailUrl&&<img src={report.metadata.thumbnailUrl} alt="TikTok video thumbnail"/>}<div><h3>{report.metadata.title||"TikTok video"}</h3><p>Creator: {report.metadata.authorName||"Not provided"}</p>{report.metadata.authorUrl&&<a href={report.metadata.authorUrl} target="_blank" rel="noreferrer">View creator profile ↗</a>}</div></div>}
 <article className="analysis"><h3>Song recognition</h3>
 {songStatus==="queued"||songStatus==="processing"?<p>Retrieving accessible audio and checking song fingerprints…</p>:null}
 {songStatus==="failed"?<p>Recognition could not be completed. {error}</p>:null}
 {songStatus==="complete"&&songResult?.matches?.length? <div className="song-list">{songResult.matches.map((m,i)=><div className="song-match" key={i}><strong>{m.title||"Unknown title"}</strong><p>{m.artist||"Unknown artist"}{m.album?" · "+m.album:""}</p><small>Matched around {Math.floor((m.matched_at_seconds||0)/60)}:{String(Math.floor((m.matched_at_seconds||0)%60)).padStart(2,"0")} · {m.provider||"Music recognition"}</small>{m.song_link&&<p><a href={m.song_link} target="_blank" rel="noreferrer">Open song match ↗</a></p>}</div>)}</div>:null}
 {songStatus==="complete"&&!songResult?.matches?.length?<p>{songResult?.message||"No song match was returned for the sampled audio."}</p>:null}
 {songStatus==="complete"&&songResult&&<p className="match-note">{songResult.message} Samples checked: {songResult.samples_checked??0}.</p>}
 {nextCursor&&<button className="continue" type="button" onClick={()=>runSongJob({cursor:nextCursor})} disabled={songStatus==="queued"||songStatus==="processing"}>CHECK NEXT 90-SECOND SEGMENT ↗</button>}
 </article>
 {report.analysis&&<article className="analysis"><h3>Professional context</h3><p>{report.analysis}</p></article>}
 <div className="report-grid"><article><h3>Recognition limits</h3><ul><li>A match is a provider result, not a guarantee of identity.</li><li>Short, noisy, remixed or sped-up audio may not match.</li><li>Later segments are checked only when you request continuation.</li></ul></article><article><h3>Source limitations</h3><ul>{report.limitations.map((x,i)=><li key={i}>{x}</li>)}</ul></article></div>
 <div className="report-actions"><button className="secondary" onClick={()=>navigator.clipboard.writeText(JSON.stringify({report,songResult},null,2))}>COPY JSON REPORT</button><span>Fetched {new Date(report.fetchedAt).toLocaleString()}</span></div>
 </section>}
 </section><footer><span>BUILT FOR AGENTS · SONG RECOGNITION API</span><span>Evidence over assumption.</span></footer></main>
}
