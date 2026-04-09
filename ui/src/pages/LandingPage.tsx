export default function LandingPage() {
  return (
    <div className="landing-page">
      <div className="landing-content">
        <h1 className="landing-heading">WhoIsMe</h1>
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
