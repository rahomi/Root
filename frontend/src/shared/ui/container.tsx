type ContainerProps = {
  children: React.ReactNode;
};

const styles: React.CSSProperties = {
  maxWidth: "960px",
  margin: "0 auto",
  padding: "24px"
};

export function Container({ children }: ContainerProps) {
  return <main style={styles}>{children}</main>;
}
