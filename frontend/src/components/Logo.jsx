import React from 'react'

export default function Logo({ size = 22, className = '', color = '#FFFFFF' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`study-guard-logo ${className}`}
      aria-label="Study Guard Logo"
    >
      <path
        d="M21 3C21 3 13.9 3.8 9.1 8.6C4.3 13.4 3.5 20.5 3.5 20.5C3.5 20.5 10.6 19.7 15.4 14.9C20.2 10.1 21 3 21 3Z"
        fill={color}
      />
      <path
        d="M4.2 19.8C7.6 16.4 12.2 11.8 15 9"
        stroke="#101522"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}
