export const PEXELS_LICENSE='https://www.pexels.com/license/';
export const PIXABAY_LICENSE='https://pixabay.com/service/license-summary/';
const landscapeHD=f=>f?.width>=1920&&f.width>f.height;
function bestVideo(files){
  const valid=files.filter(f=>f?.url&&f.width&&f.height);
  const landscape=valid.filter(f=>f.width>f.height);
  const hd=landscape.filter(landscapeHD);
  const distance=f=>Math.abs(f.width-1920)+Math.abs(f.height-1080);
  return (hd.length?hd:landscape.length?landscape:valid).sort((a,b)=>distance(a)-distance(b))[0];
}

export function stockSearchUrl(provider,query,type){
  if(provider==='pexels')return 'https://api.pexels.com/v1/'+(type==='video'?'videos/search':'search')+'?'+new URLSearchParams({query,per_page:'30',orientation:'landscape'});
  if(provider==='pixabay')return 'https://pixabay.com/api/'+(type==='video'?'videos/':'')+'?'+new URLSearchParams({q:query,per_page:'30',safesearch:'true',...(type==='photo'?{image_type:'photo'}:{video_type:'film',min_width:'1920',min_height:'1080'})});
  throw new Error('未知图库源');
}

export function pexelsCandidates(data,type){
  return (type==='photo'?data.photos||[]:data.videos||[]).flatMap(row=>{
    const file=type==='video'?bestVideo((row.video_files||[]).filter(f=>f.file_type==='video/mp4').map(f=>({...f,url:f.link}))):null;
    if(type==='video'&&!landscapeHD(file))return [];
    return {provider:'pexels',providerId:row.id,title:row.alt||'Pexels '+row.id,creator:row.photographer||row.user?.name||'',sourceUrl:row.url,
      downloadUrl:type==='photo'?row.src?.original:file?.url,thumbnailUrl:type==='photo'?row.src?.medium:row.image,
      mime:type==='photo'?'image/jpeg':'video/mp4',width:type==='photo'?row.width:file?.width,height:type==='photo'?row.height:file?.height,duration:row.duration,
      license:'Pexels License',licenseUrl:PEXELS_LICENSE,licenseEvidence:{providerApi:'https://www.pexels.com/api/documentation/',assetId:row.id},
      displayCredit:'Photos / videos provided by Pexels · '+(row.photographer||row.user?.name||''),rightsNote:'可商用与修改；保留来源/作者供API结果展示。不转售原件、不暗示人物或品牌背书、不用于不当人物描述或素材站再分发。'};
  });
}

export function pixabayCandidates(data,type){
  return (data.hits||[]).flatMap(row=>{
    const file=type==='video'?bestVideo(Object.values(row.videos||{})):null;
    if(type==='video'&&!landscapeHD(file))return [];
    return {provider:'pixabay',providerId:row.id,title:row.tags||'Pixabay '+row.id,creator:row.user||'',sourceUrl:row.pageURL,
      downloadUrl:type==='photo'?(row.imageURL||row.largeImageURL||row.webformatURL):file?.url,thumbnailUrl:type==='photo'?(row.webformatURL||row.previewURL):file?.thumbnail,
      mime:type==='photo'?'image/jpeg':'video/mp4',width:type==='video'?file?.width:row.imageURL?row.imageWidth:null,height:type==='video'?file?.height:row.imageURL?row.imageHeight:null,duration:row.duration,
      license:'Pixabay Content License',licenseUrl:PIXABAY_LICENSE,licenseEvidence:{providerApi:'https://pixabay.com/api/docs/',assetId:row.id},
      displayCredit:'Content provided by Pixabay · '+(row.user||''),rightsNote:'可商用与修改，成品无需署名；API结果展示来源。不单独转售/再分发素材，人物/商标的其他权利按用途核对。'};
  });
}
