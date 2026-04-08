import Nav from '../components/Nav'
import Footer from '../components/Footer'
import VoiceBox from '../components/VoiceBox'
import ContactForm from '../components/ContactForm'

export default function Home() {
  return (
    <>
      <Nav />

      <section id="hero">
        <img src="/assets/t12n-ai-rabbit.png" alt="t12n.ai rabbit logo" />
        <div className="label">AI Transformation Consulting</div>
        <VoiceBox />
      </section>


      <section id="about">
        <div className="section-label">About</div>
        <h2>
          Built on urgency.<br />
          <em>Grounded in reality.</em>
        </h2>
        <div className="stats-grid">
          {[
            { num: '12+', desc: 'Years in enterprise technology' },
            { num: '12+', desc: 'Business Processes transformed' },
            { num: '$16M+', desc: 'In value unlocked' },
            { num: 'Day 1', desc: 'Mindset, always' },
          ].map(({ num, desc }) => (
            <div key={num} className="stat-cell">
              <div className="stat-num">{num}</div>
              <div className="stat-desc">{desc}</div>
            </div>
          ))}
        </div>
        <div className="about-body">
          <p>I founded <strong>AI Transformation (t12n.ai)</strong> because I kept seeing the same pattern: smart leaders at great companies, frozen. Not by lack of ambition — but by the gap between knowing AI matters and knowing what to actually do about it.</p>
          <p>My work sits at the intersection of <strong>executive strategy, technical implementation, and organizational change</strong>. I don't just advise — I embed, build, and help you run.</p>
          <p>Before t12n, I led AI initiatives at Fortune 500 companies and venture-backed startups alike. I've seen what separates organizations that thrive in this moment from those that don't. It's almost never about the technology.</p>
          <p>It's about <strong>speed of decision, clarity of ownership, and the courage to move before everything is certain</strong>. That's what I help you build.</p>
        </div>
      </section>


      <section id="services">
        <div className="section-label">What I do</div>
        <div className="services-grid">
          {[
            {
              num: '01',
              title: 'AI Strategy & Roadmapping',
              desc: 'From audit to action plan in 30 days. Where are you losing ground? Where can AI compound your advantage? We map it, prioritize it, and make it executable.',
            },
            {
              num: '02',
              title: 'Executive Alignment',
              desc: "The hardest part of AI transformation isn't the AI. I facilitate leadership alignment that turns cautious committees into decisive sponsors.",
            },
            {
              num: '03',
              title: 'Implementation Oversight',
              desc: 'I embed with your teams to ensure strategy becomes working systems. From vendor selection to go-live, with zero tolerance for vaporware.',
            },
          ].map(({ num, title, desc }) => (
            <div key={num} className="service-card">
              <div className="service-num">{num}</div>
              <div className="service-title">{title}</div>
              <div className="service-desc">{desc}</div>
            </div>
          ))}
        </div>
      </section>


      <section id="contact">
        <div className="section-label">Contact</div>
        <h2 className="contact-heading">
          Let's talk about<br />
          <em>what's actually blocking you.</em>
        </h2>
        <ContactForm />
      </section>


      <Footer />
    </>
  )
}
