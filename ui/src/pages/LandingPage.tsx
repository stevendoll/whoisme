export default function LandingPage() {
  return (
    <div className="landing-page">
      <div className="landing-content">
        <img src="/assets/whoisme-horizontal.png" alt="WhoIsMe" className="landing-logo" />
        <p className="landing-subheading">Your professional story, told in your voice.</p>
        <p className="landing-body">
          A short conversational interview that helps you articulate who you are, what you do,
          and what drives you. Answer a few questions and we'll craft a polished professional
          profile that sounds like you.
        </p>
        <a href="#/interview" className="btn-primary landing-start">
          Start interview
        </a>
      </div>
    </div>
  )
}
