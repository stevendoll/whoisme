export default function Nav() {
  const isHistory = window.location.hash === '#/history'

  return (
    <nav>
      <a href="#">
        <img src="/assets/t12n-ai-name.png" alt="t12n.ai" />
      </a>
      <ul>
        {!isHistory && (
          <>
            <li><a href="#about">About</a></li>
            <li><a href="#services">Services</a></li>
            <li><a href="#contact">Contact</a></li>
          </>
        )}
        {isHistory && (
          <li><a href="#">← Home</a></li>
        )}
      </ul>
    </nav>
  )
}
