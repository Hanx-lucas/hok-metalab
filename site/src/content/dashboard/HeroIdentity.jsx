import React from 'react';
import portraits from '../assets/hero-art/portraits.json';
export function HeroPortrait({id,name,size='normal'}){
 const canonical=[50701,50702].includes(id)?507:id;
 const src=portraits[String(canonical)];
 return <span className={`hok-portrait hok-portrait--${size}`} aria-hidden={!src||undefined}>{src?<img src={src} alt={`${name}头像`} loading="lazy" decoding="async"/>:<span>{name?.slice(0,1)||'?'}</span>}</span>;
}
const paths={
 '对抗路':<><path d="M5 3l14 14-2 2L3 5zM14 18l4-4M18 18l3 3M19 3L5 17l2 2L21 5zM10 18l-4-4M6 18l-3 3"/></>,
 '打野':<><path d="M12 2l5 11-5 4-5-4zM8 18h8M10 18v4M14 18v4M4 7l3 3M20 7l-3 3"/></>,
 '中路':<><circle cx="12" cy="12" r="8"/><path d="M12 3l3 9-3 9-3-9zM3 12h18"/></>,
 '发育路':<><path d="M7 3c10 4 10 14 0 18M7 3v18M3 12h18M17 8l4 4-4 4"/></>,
 '游走':<><path d="M12 2l8 4v7c0 5-8 9-8 9s-8-4-8-9V6zM8 11l3 3 5-6"/></>
};
export function LaneIcon({lane}){return <svg className="sb-lane-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">{paths[lane]}</svg>}
